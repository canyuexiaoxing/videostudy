"""Temporary GPU playback copies. No AI requests or CPU encoding fallback."""
import json
import os
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix='/compatibility')
slot = threading.Lock()
state_lock = threading.RLock()
active = {}
TTL_SECONDS = 24 * 3600


@router.on_event('startup')
def start_janitor():
    # An interrupted conversion cannot be resumed after a service restart.
    base = root()
    if base.exists():
        for directory in base.iterdir():
            try:
                job_path(base, directory.name)
                state_file = directory / 'status.json'
                state = json.loads(state_file.read_text(encoding='utf-8'))
                if state.get('status') in ('queued', 'processing'):
                    state.update(status='failed', error='转码服务已重启，请重新生成兼容副本')
                    save(directory, state)
                    (directory / 'input').unlink(missing_ok=True)
                    (directory / 'playback.mp4').unlink(missing_ok=True)
            except (ValueError, OSError):
                pass
    def run():
        while True:
            cleanup_expired()
            time.sleep(300)
    threading.Thread(target=run, daemon=True).start()


def root():
    return Path(os.environ.get('MEDIA_TEMP_DIR', '../.local/uploads')).resolve() / 'compatibility'


def job_path(base, identity):
    if str(uuid.UUID(identity)) != identity:
        raise ValueError('invalid_job_id')
    return base / identity


def progress_percent(out_time_us, duration):
    return min(99, max(0, int(out_time_us / 1_000_000 / max(duration, .001) * 100)))


def command(source, output, audio_codec='aac'):
    return ['ffmpeg', '-hide_banner', '-y', '-hwaccel', 'cuda', '-i', str(source),
            '-map', '0:v:0', '-map', '0:a:0?', '-c:v', 'h264_nvenc', '-preset', 'p4',
            '-rc', 'vbr', '-cq', '23', '-b:v', '0', '-pix_fmt', 'yuv420p',
            '-c:a', 'copy' if audio_codec == 'aac' else 'aac',
            '-movflags', '+faststart', '-progress', 'pipe:1', '-nostats', str(output)]


def probe(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format',
                             '-of', 'json', str(path)], capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise ValueError('无法读取原视频格式')
    return json.loads(result.stdout)


def save(directory, state):
    target = directory / 'status.json'
    temp = directory / 'status.tmp'
    temp.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
    temp.replace(target)


def cleanup_expired():
    base = root()
    if not base.exists():
        return
    with state_lock:
        for directory in base.iterdir():
            if not directory.is_dir() or directory.name in active:
                continue
            if time.time() - directory.stat().st_mtime > TTL_SECONDS:
                try:
                    job_path(base, directory.name)
                    shutil.rmtree(directory)
                except (ValueError, OSError):
                    pass


def encode(identity, directory, cancel):
    state = {'id': identity, 'status': 'processing', 'progress': 0, 'encoder': 'h264_nvenc'}
    process = None
    watchdog = None
    try:
        data = probe(directory / 'input')
        duration = float(data['format']['duration'])
        audio = next((s['codec_name'] for s in data['streams'] if s['codec_type'] == 'audio'), 'aac')
        with state_lock:
            if cancel.is_set():
                return
            save(directory, state)
            log = (directory / 'ffmpeg.log').open('w', encoding='utf-8')
            process = subprocess.Popen(command(directory / 'input', directory / 'playback.mp4', audio),
                                       stdout=subprocess.PIPE, stderr=log, text=True)
            active[identity]['process'] = process
        watchdog = threading.Timer(2 * 3600, process.kill)
        watchdog.daemon = True
        watchdog.start()
        try:
            for line in process.stdout:
                if line.startswith('out_time_us='):
                    try:
                        state['progress'] = progress_percent(int(line.split('=')[1]), duration)
                    except ValueError:
                        continue
                    with state_lock:
                        if not cancel.is_set():
                            save(directory, state)
            code = process.wait()
        finally:
            log.close()
        if cancel.is_set():
            return
        if code:
            detail = (directory / 'ffmpeg.log').read_text(encoding='utf-8')[-3000:]
            raise ValueError('显卡转码失败；请确认 NVENC、CUDA 驱动和容器 video 权限可用。' + detail)
        converted = probe(directory / 'playback.mp4')
        if abs(float(converted['format']['duration']) - duration) > .25:
            raise ValueError('转换后的时长与原视频不一致，未切换播放')
        state.update(status='completed', progress=100)
        with state_lock:
            if not cancel.is_set():
                save(directory, state)
    except Exception as error:
        with state_lock:
            if not cancel.is_set():
                state.update(status='failed', error=str(error))
                save(directory, state)
                (directory / 'playback.mp4').unlink(missing_ok=True)
    finally:
        if watchdog:
            watchdog.cancel()
        with state_lock:
            (directory / 'input').unlink(missing_ok=True)
            active.pop(identity, None)
            if cancel.is_set():
                shutil.rmtree(directory, ignore_errors=True)
        slot.release()


class StartRequest(BaseModel):
    id: str


@router.get('/capabilities')
def capabilities():
    cleanup_expired()
    try:
        result = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=s=640x360',
                                 '-frames:v', '1', '-c:v', 'h264_nvenc', '-f', 'null', '-'],
                                capture_output=True, text=True, timeout=20)
        return {'available': result.returncode == 0, 'encoder': 'h264_nvenc',
                'error': None if result.returncode == 0 else '后台显卡编码不可用，请检查驱动和 GPU 容器配置'}
    except (OSError, subprocess.TimeoutExpired):
        return {'available': False, 'error': '后台 FFmpeg 或显卡编码不可用'}


@router.post('')
def start(request: StartRequest):
    try:
        directory = job_path(root(), request.id)
    except ValueError:
        raise HTTPException(400, 'invalid_job_id')
    if not (directory / 'input').is_file():
        raise HTTPException(404, 'upload_not_found')
    if not slot.acquire(blocking=False):
        raise HTTPException(429, '显卡转码正在运行，请稍后再试')
    with state_lock:
        cancel = threading.Event()
        state = {'id': request.id, 'status': 'queued', 'progress': 0}
        save(directory, state)
        active[request.id] = {'cancel': cancel, 'process': None}
        threading.Thread(target=encode, args=(request.id, directory, cancel), daemon=True).start()
    return state


@router.get('/{identity}')
def status(identity: str):
    cleanup_expired()
    try:
        with state_lock:
            return json.loads((job_path(root(), identity) / 'status.json').read_text(encoding='utf-8'))
    except (ValueError, OSError):
        raise HTTPException(404, 'job_not_found')


@router.delete('/{identity}')
def delete(identity: str):
    try:
        directory = job_path(root(), identity)
    except ValueError:
        raise HTTPException(400, 'invalid_job_id')
    with state_lock:
        job = active.get(identity)
        if job:
            job['cancel'].set()
            if job['process'] and job['process'].poll() is None:
                job['process'].terminate()
        else:
            shutil.rmtree(directory, ignore_errors=True)
    return {'status': 'deleted'}

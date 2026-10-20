import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import threading
import json
import compatible_playback as playback
from compatible_playback import command, job_path, progress_percent


class CompatiblePlaybackTests(unittest.TestCase):
    def test_only_gpu_encoder_and_audio_copy(self):
        args = command(Path('input'), Path('output.mp4'))
        self.assertEqual(args[args.index('-c:v') + 1], 'h264_nvenc')
        self.assertEqual(args[args.index('-c:a') + 1], 'copy')
        self.assertIn('yuv420p', args)
        self.assertNotIn('libopenh264', args)
        self.assertNotIn('-ss', args)
        self.assertNotIn('-r', args)

    def test_native_auto_uses_cpu_when_nvenc_unavailable(self):
        with patch.dict(playback.os.environ, {'FRAMEWISE_DEVICE_MODE':'auto'}), patch.object(playback, 'encoder_available', side_effect=lambda x:x=='libopenh264'):
            self.assertEqual(playback.choose_encoder(),'libopenh264')

    def test_native_cpu_never_probes_gpu(self):
        with patch.dict(playback.os.environ, {'FRAMEWISE_DEVICE_MODE':'cpu'}), patch.object(playback, 'encoder_available', return_value=True) as probe:
            self.assertEqual(playback.choose_encoder(),'libopenh264')
            probe.assert_called_once_with('libopenh264')

    def test_strict_gpu_and_docker_never_cpu_fallback(self):
        for mode in ('gpu',''):
            with patch.dict(playback.os.environ, {'FRAMEWISE_DEVICE_MODE':mode}), patch.object(playback, 'encoder_available', return_value=False) as probe:
                with self.assertRaises(ValueError):playback.choose_encoder()
                probe.assert_called_once_with('h264_nvenc')

    def test_cpu_encode_uses_software_decode_and_preserves_timing(self):
        args=command('input','output','opus','libopenh264')
        self.assertNotIn('-hwaccel',args)
        self.assertEqual(args[args.index('-c:v')+1],'libopenh264')
        self.assertNotIn('-r',args)
        self.assertNotIn('-ss',args)

    def test_reject_path_traversal(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                job_path(Path(root), '../escape')

    def test_progress_does_not_claim_completion_early(self):
        self.assertEqual(progress_percent(5_000_000, 10), 50)
        self.assertEqual(progress_percent(15_000_000, 10), 99)

    def test_non_aac_audio_is_encoded(self):
        args = command(Path('input'), Path('output.mp4'), 'opus')
        self.assertEqual(args[args.index('-c:a') + 1], 'aac')

    def test_decode_failure_cleans_uploaded_video_and_partial_copy(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            (directory / 'input').write_bytes(b'private video')
            (directory / 'playback.mp4').write_bytes(b'partial')
            playback.slot.acquire()
            with patch.object(playback, 'probe', side_effect=ValueError('bad video')):
                playback.encode('test', directory, threading.Event())
            state = json.loads((directory / 'status.json').read_text(encoding='utf-8'))
            self.assertEqual(state['status'], 'failed')
            self.assertFalse((directory / 'input').exists())
            self.assertFalse((directory / 'playback.mp4').exists())
            self.assertFalse(playback.slot.locked())

    def test_cancel_cleans_entire_job_and_releases_gpu_slot(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / 'job'
            directory.mkdir()
            (directory / 'input').write_bytes(b'private video')
            cancel = threading.Event(); cancel.set()
            playback.slot.acquire()
            with patch.object(playback, 'probe', return_value={'format': {'duration': 10}, 'streams': []}):
                playback.encode('test', directory, cancel)
            self.assertFalse(directory.exists())
            self.assertFalse(playback.slot.locked())


class RetentionTests(unittest.TestCase):
    def test_keep_48_hour_copy_and_expire_after_72_hours(self):
        import os,time,uuid
        self.assertEqual(playback.TTL_SECONDS,72*3600)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);now=time.time()
            fresh=root/str(uuid.uuid4());old=root/str(uuid.uuid4());fresh.mkdir();old.mkdir()
            (fresh/'playback.mp4').write_bytes(b'fixture');(old/'playback.mp4').write_bytes(b'fixture')
            os.utime(fresh,(now-48*3600,now-48*3600));os.utime(old,(now-73*3600,now-73*3600))
            with patch.object(playback,'root',return_value=root):playback.cleanup_expired()
            self.assertTrue(fresh.exists());self.assertFalse(old.exists())

    def test_running_job_is_not_deleted_even_if_older_than_retention(self):
        import os,time,uuid
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);identity=str(uuid.uuid4());job=root/identity;job.mkdir()
            old=time.time()-100*3600;os.utime(job,(old,old))
            with patch.object(playback,'root',return_value=root),patch.dict(playback.active,{identity:{}},clear=True):
                playback.cleanup_expired()
            self.assertTrue(job.exists())

if __name__ == '__main__':
    unittest.main()

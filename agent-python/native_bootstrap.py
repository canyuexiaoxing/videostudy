"""Docker-free Windows worker entry point. Configuration contains paths, never secrets."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import secrets
import shutil
import sys
import uuid
from native_devices import DevicePolicyError,configure_dll_directories,probe_all,select_devices

CONFIG_FIELDS={'schemaVersion','mode','dataDir','modelDir','personPython','ffmpegDir','javaDir','dllDirs','probeTimeoutSeconds'}

def validate_config(value):
    if not isinstance(value,dict) or set(value)-CONFIG_FIELDS:raise ValueError('invalid_native_config_fields')
    if value.get('schemaVersion',1)!=1:raise ValueError('unsupported_native_config_version')
    mode=value.get('mode','auto')
    if mode not in {'auto','gpu','cpu'}:raise ValueError('invalid_device_mode')
    data=value.get('dataDir')
    if not isinstance(data,str) or not Path(data).is_absolute():raise ValueError('dataDir_must_be_absolute')
    result=dict(value,mode=mode,dataDir=str(Path(data).resolve()))
    for key in ('modelDir','personPython','ffmpegDir','javaDir'):
        if key in value and (not isinstance(value[key],str) or not Path(value[key]).is_absolute()):raise ValueError(key+'_must_be_absolute')
    dlls=value.get('dllDirs',[])
    if not isinstance(dlls,list) or any(not isinstance(p,str) or not Path(p).is_absolute() for p in dlls):raise ValueError('dllDirs_must_be_absolute')
    timeout=value.get('probeTimeoutSeconds',45)
    if type(timeout) not in (int,float) or not 1<=timeout<=120:raise ValueError('invalid_probe_timeout')
    return result

def configure_environment(config):
    data=Path(config['dataDir']);data.mkdir(parents=True,exist_ok=True)
    locations={'MODEL_DIR':Path(config.get('modelDir',str(data/'models'))),'MEDIA_TEMP_DIR':data/'uploads','KEYFRAME_DIR':data/'keyframes','MODEL_LOG_DIR':data/'logs','USERPROFILE':data/'profile','APPDATA':data/'profile/AppData/Roaming','LOCALAPPDATA':data/'profile/AppData/Local','CUDA_CACHE_PATH':data/'cache/cuda','MPLCONFIGDIR':data/'cache/matplotlib','HOME':data/'profile','HF_HOME':data/'cache/huggingface','HUGGINGFACE_HUB_CACHE':data/'cache/huggingface/hub','XDG_CACHE_HOME':data/'cache','PADDLE_HOME':data/'cache/paddle','PADDLE_PDX_CACHE_HOME':data/'cache/paddlex','TORCH_HOME':data/'cache/torch','YOLO_CONFIG_DIR':data/'cache/ultralytics','TEMP':data/'tmp','TMP':data/'tmp'}
    for key,path in locations.items():path.mkdir(parents=True,exist_ok=True);os.environ[key]=str(path)
    os.environ.update(FRAMEWISE_DEVICE_MODE=config['mode'],WHISPER_MODEL='small',WHISPER_BATCH_SIZE='4',PERSON_SEGMENTATION='off',PYTHONIOENCODING='utf-8',HF_HUB_OFFLINE='1',PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK='True',FRAMEWISE_RUNTIME_STATE=str(data/'runtime/runtime-state.json'))
    os.environ['PERSON_PYTHON']=config.get('personPython',str(Path(sys.executable).parent.parent/'person/python.exe'))
    os.environ['FRAMEWISE_DLL_DIRS']=json.dumps(config.get('dllDirs',[]))
    additions=[config[key] for key in ('ffmpegDir','javaDir') if config.get(key)]
    os.environ['PATH']=os.pathsep.join([*additions,*config.get('dllDirs',[]),os.environ.get('PATH','')])
    configure_dll_directories()

def apply_devices(state):
    devices=state['devices'];whisper=devices['whisper'];person=devices['person']
    os.environ.update(WHISPER_DEVICE=whisper,WHISPER_COMPUTE_TYPE='float16' if whisper=='cuda' else 'int8',WHISPER_BATCH_SIZE='4' if whisper=='cuda' else '0',OCR_DEVICE='gpu:0' if devices['ocr']=='cuda' else 'cpu',PERSON_DEVICE=person)

def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('x',encoding='utf-8') as output:
            json.dump(value,output,ensure_ascii=False,indent=2);output.flush();os.fsync(output.fileno())
        os.replace(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)

def memory_report():
    if os.name!='nt':return {'totalBytes':None,'availableBytes':None}
    class Memory(ctypes.Structure):
        _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong),('totalPhys',ctypes.c_ulonglong),('availPhys',ctypes.c_ulonglong),('totalPageFile',ctypes.c_ulonglong),('availPageFile',ctypes.c_ulonglong),('totalVirtual',ctypes.c_ulonglong),('availVirtual',ctypes.c_ulonglong),('availExtendedVirtual',ctypes.c_ulonglong)]
    memory=Memory();memory.length=ctypes.sizeof(memory)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):return {'totalBytes':None,'availableBytes':None}
    return {'totalBytes':memory.totalPhys,'availableBytes':memory.availPhys}

def prepare(config):
    configure_environment(config)
    probes=probe_all(config['mode'],sys.executable,os.environ['PERSON_PYTHON'],config.get('probeTimeoutSeconds',45))
    disk=shutil.disk_usage(config['dataDir'])
    report={'schemaVersion':1,'mode':config['mode'],'memory':memory_report(),'disk':{'totalBytes':disk.total,'freeBytes':disk.free},'modules':{},'available':False}
    for name,result in probes.items():
        gpu=result.get('gpu',{}).get('ok',False);cpu=result.get('cpu',{}).get('ok',False)
        device='cuda' if config['mode']!='cpu' and gpu else 'cpu'
        available=gpu if config['mode']=='gpu' else cpu if config['mode']=='cpu' else gpu or cpu
        report['modules']['yolo' if name=='person' else name]={'device':device,'available':available,'reason':None if available and (device=='cuda' or config['mode']=='cpu') else 'gpu_unavailable_cpu_fallback' if available else 'runtime_unavailable','probes':result}
    path=Path(config['dataDir'])/'runtime'
    try:
        state=select_devices(config['mode'],probes)
    except DevicePolicyError:
        atomic_json(path/'hardware-report.json',report)
        atomic_json(path/'runtime-state.json',{'mode':config['mode'],'available':False,'devices':{},'fallbacks':[]})
        raise
    model_root=Path(os.environ['MODEL_DIR'])
    required={'whisper':[model_root/'faster-whisper-small/model.bin'],'ocr':[model_root/'paddleocr/PP-OCRv6_medium_det_infer/inference.json',model_root/'paddleocr/PP-OCRv6_medium_rec_infer/inference.json'],'person':[model_root/'yolo26/yolo26n-seg.pt']}
    for name,paths in required.items():
        module=report['modules']['yolo' if name=='person' else name]
        module['device']=state['devices'][name]
        if any(not path.is_file() for path in paths):
            module.update(available=False,reason='missing_models')
            if name not in state['pending']:state['pending'].append(name)
    report['available']=not state['pending'];report['devices']=state['devices'];report['fallbacks']=state['fallbacks'];report['pending']=state['pending']
    atomic_json(path/'hardware-report.json',report);atomic_json(path/'runtime-state.json',dict(state,available=True))
    apply_devices(state)
    return report

def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);parser.add_argument('--host',default='127.0.0.1',choices=['127.0.0.1']);parser.add_argument('--port',type=int,default=8000);parser.add_argument('--probe-only',action='store_true');args=parser.parse_args(argv)
    if not 1<=args.port<=65535:parser.error('port must be between 1 and 65535')
    try:
        config=validate_config(json.loads(Path(args.config).read_text(encoding='utf-8-sig')))
        report=prepare(config)
    except (OSError,ValueError,DevicePolicyError) as error:
        print(json.dumps({'event':'native_startup_failed','errorType':type(error).__name__}),flush=True);return 2
    print(json.dumps({'event':'native_hardware_ready','mode':report['mode'],'modules':report['modules']}),flush=True)
    if args.probe_only:return 0
    import uvicorn
    from app import app
    token=os.environ.get('FRAMEWISE_RUNTIME_TOKEN','')
    application=RuntimeTokenMiddleware(app,token) if token else app
    uvicorn.run(application,host=args.host,port=args.port,log_level='info')
    return 0

class RuntimeTokenMiddleware:
    """Constrain the native worker to its owning desktop launch, including /health."""
    def __init__(self,app,token):self.app=app;self.token=token.encode('utf-8')
    async def __call__(self,scope,receive,send):
        if scope['type']=='http':
            values=[value for key,value in scope.get('headers',[]) if key.lower()==b'x-framewise-runtime']
            if len(values)!=1 or not secrets.compare_digest(values[0],self.token):
                await send({'type':'http.response.start','status':403,'headers':[(b'content-type',b'application/json')]})
                await send({'type':'http.response.body','body':b'{"detail":"native_runtime_forbidden"}'})
                return
        await self.app(scope,receive,send)

if __name__=='__main__':raise SystemExit(main())




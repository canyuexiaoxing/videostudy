"""Native device policy. Framework probes run in bounded, isolated interpreters."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

MODULES=('whisper','ocr','person')
_DLL_HANDLES=[]
_DLL_PATHS=set()

class DevicePolicyError(RuntimeError):
    pass

# Import DLL policy before any framework. Each process imports exactly one runtime.
PROBE_SCRIPTS={
 'ocr': '''import paddle
paddle.set_device('gpu:0' if device=='cuda' else 'cpu')
x=paddle.ones([2,2]); y=paddle.matmul(x,x); assert float(y.sum().numpy())==8.0
if device=='cuda': paddle.device.cuda.synchronize()
''',
 'person': '''import torch
x=torch.ones((2,2),device=device); y=torch.matmul(x,x); assert y.sum().item()==8.0
if device=='cuda': torch.cuda.synchronize()
''',
 'whisper': '''import ctranslate2
import numpy as np
from pathlib import Path
root=Path(os.environ['MODEL_DIR'])/'faster-whisper-small'
if not (root/'model.bin').is_file():
 assert ctranslate2.get_supported_compute_types(device), 'runtime_unavailable'
 print('FRAMEWISE_PROBE_MISSING_MODELS');sys.exit(3)
model=ctranslate2.models.Whisper(str(root),device=device,compute_type='float16' if device=='cuda' else 'int8')
features=ctranslate2.StorageView.from_array(np.zeros((1,80,3000),dtype=np.float32))
encoded=model.encode(features)
assert encoded.shape[0]==1
'''
}

def configure_dll_directories(paths=None):
    """Retain handles: closing add_dll_directory handles removes the search path."""
    supplied=paths if paths is not None else json.loads(os.environ.get('FRAMEWISE_DLL_DIRS','[]'))
    base=Path(sys.executable).parent
    candidates=[*supplied,base,base/'DLLs',base/'Lib/site-packages/torch/lib',base/'Lib/site-packages/paddle/libs',base/'Lib/site-packages/ctranslate2']
    candidates.extend((base/'Lib/site-packages/nvidia').glob('*/bin'))
    for path in candidates:
        path=Path(path).resolve()
        if not path.is_dir():continue
        # CTranslate2 loads cuBLAS via LoadLibrary, which also needs PATH.
        current=os.environ.get('PATH','').split(os.pathsep)
        if str(path) not in current:os.environ['PATH']=os.pathsep.join([str(path),*current])
        if str(path) in _DLL_PATHS:continue
        if hasattr(os,'add_dll_directory'):_DLL_HANDLES.append(os.add_dll_directory(str(path)))
        _DLL_PATHS.add(str(path))

def probe_module(module,python,device,timeout=45):
    started=time.monotonic()
    script="import os,sys\nfrom native_devices import configure_dll_directories\nconfigure_dll_directories()\ndevice="+repr(device)+'\n'+PROBE_SCRIPTS[module]+"\nprint('FRAMEWISE_PROBE_OK')\n"
    env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')
    try:
        result=subprocess.run([str(python),'-c',script],cwd=str(Path(__file__).parent),env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        ok=result.returncode==0 and 'FRAMEWISE_PROBE_OK' in result.stdout
        # Never copy framework stderr: it can contain paths, environment or external URLs.
        reason=None if ok else 'missing_models' if result.returncode==3 and 'FRAMEWISE_PROBE_MISSING_MODELS' in result.stdout else 'runtime_operation_failed'
        return {'ok':ok,'reason':reason,'exitCode':result.returncode,'elapsedMs':round((time.monotonic()-started)*1000)}
    except subprocess.TimeoutExpired:
        return {'ok':False,'reason':'timeout','elapsedMs':round((time.monotonic()-started)*1000)}
    except OSError:
        return {'ok':False,'reason':'interpreter_unavailable','elapsedMs':round((time.monotonic()-started)*1000)}

def probe_all(mode,python,person_python,timeout=45):
    if mode not in {'auto','gpu','cpu'}:raise ValueError('invalid_device_mode')
    return {name:{kind:probe_module(name,person_python if name=='person' else python,device,timeout) for kind,device in [('gpu','cuda'),('cpu','cpu')] if mode!='cpu' or kind=='cpu'} for name in MODULES}

def select_devices(mode,probes):
    if mode not in {'auto','gpu','cpu'}:raise ValueError('invalid_device_mode')
    devices={};fallbacks=[];failed=[];pending=[]
    def ok(value):return (value.get('ok',False) or value.get('reason')=='missing_models') if isinstance(value,dict) else bool(value)
    for module in MODULES:
        result=probes.get(module,{})
        if mode!='cpu' and ok(result.get('gpu')):devices[module]='cuda'
        elif mode!='gpu' and ok(result.get('cpu')):
            devices[module]='cpu'
            if mode=='auto':fallbacks.append(module)
        else:failed.append(module)
        selected=result.get('gpu' if devices.get(module)=='cuda' else 'cpu',{})
        if isinstance(selected,dict) and selected.get('reason')=='missing_models':pending.append(module)
    if failed:raise DevicePolicyError('native_device_unavailable:'+','.join(failed))
    return {'mode':mode,'devices':devices,'fallbacks':fallbacks,'pending':pending}

def allow_cpu_fallback(error,device):
    text=str(error).lower()
    return os.environ.get('FRAMEWISE_DEVICE_MODE')=='auto' and device in {'cuda','gpu:0','0'} and ('out of memory' in text or 'resourceexhausted' in text or 'cuda_error_out_of_memory' in text)

def record_fallback(module,error,task='unbound'):
    """One safe event per fallback; detailed bodies and environment are excluded."""
    from model_diagnostics import record_event
    record_event('stage_failed',task,operation={'whisper':'transcription','ocr':'frame_pipeline','person':'person_selection'}[module],stage='fallback',device='cuda',reason='out_of_memory',error_type=type(error).__name__,status='failed')
    report_path=os.environ.get('FRAMEWISE_RUNTIME_STATE')
    if report_path:
        try:
            from native_bootstrap import atomic_json
            path=Path(report_path);state=json.loads(path.read_text(encoding='utf-8'))
            state['devices'][module]='cpu'
            state['fallbacks']=sorted(set(state.get('fallbacks',[])+[module]))
            atomic_json(path,state)
        except (OSError,ValueError,KeyError):pass



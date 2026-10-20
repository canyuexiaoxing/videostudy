"""Own a Windows process tree. Closing the desktop's stdin pipe kills only this launch's job."""
import os,sys,subprocess,threading,time,ctypes,signal
from ctypes import wintypes

def job_for(process):
 if os.name!='nt':return None
 kernel=ctypes.WinDLL('kernel32',use_last_error=True)
 kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR];kernel.CreateJobObjectW.restype=wintypes.HANDLE
 kernel.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD];kernel.SetInformationJobObject.restype=wintypes.BOOL
 kernel.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE];kernel.AssignProcessToJobObject.restype=wintypes.BOOL
 kernel.CloseHandle.argtypes=[wintypes.HANDLE]
 class Basic(ctypes.Structure):_fields_=[('processTime',ctypes.c_longlong),('jobTime',ctypes.c_longlong),('flags',wintypes.DWORD),('minWorking',ctypes.c_size_t),('maxWorking',ctypes.c_size_t),('processes',wintypes.DWORD),('affinity',ctypes.c_size_t),('priority',wintypes.DWORD),('scheduling',wintypes.DWORD)]
 class IO(ctypes.Structure):_fields_=[(name,ctypes.c_ulonglong) for name in ('readOps','writeOps','otherOps','readBytes','writeBytes','otherBytes')]
 class Extended(ctypes.Structure):_fields_=[('basic',Basic),('io',IO),('processMemory',ctypes.c_size_t),('jobMemory',ctypes.c_size_t),('peakProcess',ctypes.c_size_t),('peakJob',ctypes.c_size_t)]
 handle=kernel.CreateJobObjectW(None,None)
 if not handle:raise OSError('native_job_create_failed')
 info=Extended();info.basic.flags=0x00002000
 if not kernel.SetInformationJobObject(handle,9,ctypes.byref(info),ctypes.sizeof(info)) or not kernel.AssignProcessToJobObject(handle,wintypes.HANDLE(int(process._handle))):
  kernel.CloseHandle(handle);raise OSError('native_job_assign_failed')
 return kernel,handle

def main():
 if len(sys.argv)>=3 and sys.argv[1]=='--_launch-gated':
  # Parent assigns this gate to its Job before permitting any executable to start.
  if os.read(sys.stdin.fileno(),1)!=b'1':return 0
  return subprocess.Popen(sys.argv[2:],stdin=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)).wait()
 if len(sys.argv)<3 or sys.argv[1]!='--':return 2
 kwargs={'stdin':subprocess.PIPE,'creationflags':getattr(subprocess,'CREATE_NO_WINDOW',0)}
 process=subprocess.Popen([sys.executable,str(__file__),'--_launch-gated',*sys.argv[2:]],**kwargs);job=None;closed=threading.Event()
 try:
  job=job_for(process)
  process.stdin.write(b'1');process.stdin.flush();process.stdin.close()
  def input_closed():
   try:
    # Avoid a daemon holding BufferedReader's lock at interpreter shutdown.
    while os.read(sys.stdin.fileno(),1):pass
   finally:closed.set()
  threading.Thread(target=input_closed,daemon=True).start()
  while process.poll() is None and not closed.wait(.2):pass
  if process.poll() is None:
   process.terminate()
   try:process.wait(timeout=4)
   except subprocess.TimeoutExpired:process.kill()
  return process.wait(timeout=5)
 finally:
  if job:job[0].CloseHandle(job[1])
  elif process.poll() is None:process.kill()
  if process.stdin and not process.stdin.closed:process.stdin.close()
if __name__=='__main__':raise SystemExit(main())



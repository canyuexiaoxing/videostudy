"""Real Windows Job Object lifecycle tests; only fixture process IDs are touched."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
HOST=Path(__file__).with_name('native_process_host.py')
QA=ROOT/'.local/qa/native-job-host'

@unittest.skipUnless(os.name=='nt','Windows Job Objects')
class WindowsJobHostTests(unittest.TestCase):
 def setUp(self):
  QA.mkdir(parents=True,exist_ok=True)
  self.tmp=tempfile.TemporaryDirectory(dir=QA);self.addCleanup(self.tmp.cleanup)
  self.folder=Path(self.tmp.name);self.children=[];self.pids=[]
  self.addCleanup(self.cleanup_processes)
  self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
  self.kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];self.kernel.OpenProcess.restype=wintypes.HANDLE
  self.kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)];self.kernel.GetExitCodeProcess.restype=wintypes.BOOL
  self.kernel.TerminateProcess.argtypes=[wintypes.HANDLE,wintypes.UINT];self.kernel.TerminateProcess.restype=wintypes.BOOL
  self.kernel.CloseHandle.argtypes=[wintypes.HANDLE];self.kernel.CloseHandle.restype=wintypes.BOOL
 def alive(self,pid):
  handle=self.kernel.OpenProcess(0x1000,False,pid)
  if not handle:return False
  try:
   code=wintypes.DWORD();return bool(self.kernel.GetExitCodeProcess(handle,ctypes.byref(code))) and code.value==259
  finally:self.kernel.CloseHandle(handle)
 def cleanup_processes(self):
  for child in self.children:
   if child.poll() is None:child.kill()
   child.wait(timeout=5)
   if child.stdin and not child.stdin.closed:child.stdin.close()
   if child.stdout:child.stdout.close()
   if child.stderr:child.stderr.close()
  # Every PID here was read from this test's generated fixture, never discovery.
  for pid in self.pids:
   handle=self.kernel.OpenProcess(0x0001,False,pid)
   if handle:
    self.kernel.TerminateProcess(handle,99);self.kernel.CloseHandle(handle)
 def wait_for(self,predicate,seconds=8):
  until=time.monotonic()+seconds
  while time.monotonic()<until:
   if predicate():return
   time.sleep(.03)
  self.fail('Timed out waiting for owned fixture process lifecycle')
 def fixture(self,normal_exit=False,host_script=HOST):
  target=self.folder/'pids.json'
  script=self.folder/'fixture.py'
  script.write_text("import json,os,subprocess,sys,time\nfrom pathlib import Path\nchild=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],creationflags=subprocess.CREATE_NO_WINDOW)\nPath(sys.argv[1]).write_text(json.dumps([os.getpid(),child.pid]))\n"+("time.sleep(.3);sys.exit(7)\n" if normal_exit else "time.sleep(60)\n"),encoding='utf-8')
  host=subprocess.Popen([sys.executable,str(host_script),'--',sys.executable,str(script),str(target)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
  self.children.append(host)
  self.wait_for(target.exists)
  self.pids=json.loads(target.read_text());self.assertTrue(all(self.alive(pid) for pid in self.pids))
  return host
 def test_parent_stdin_eof_reaps_child_and_grandchild(self):
  host=self.fixture();host.stdin.close();host.wait(timeout=8)
  self.wait_for(lambda:not any(self.alive(pid) for pid in self.pids))
 def test_forcibly_killed_host_reaps_child_and_grandchild(self):
  host=self.fixture();host.kill();host.wait(timeout=8)
  self.wait_for(lambda:not any(self.alive(pid) for pid in self.pids))
 def test_normal_child_exit_preserves_unrelated_process_and_exit_code(self):
  unrelated=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],creationflags=subprocess.CREATE_NO_WINDOW);self.children.append(unrelated)
  host=self.fixture(normal_exit=True);self.assertEqual(host.wait(timeout=8),7,host.stderr.read().decode(errors="replace"))
  self.wait_for(lambda:not any(self.alive(pid) for pid in self.pids))
  self.assertIsNone(unrelated.poll())
 def test_fast_descendant_cannot_escape_slow_job_assignment(self):
  runner=self.folder/'delayed_host.py'
  runner.write_text("import sys,time\nsys.path.insert(0,"+repr(str(HOST.parent))+")\nimport native_process_host as host\noriginal=host.job_for\ndef delayed(process):\n time.sleep(.6)\n return original(process)\nhost.job_for=delayed\nraise SystemExit(host.main())\n",encoding='utf-8')
  host=self.fixture(host_script=runner)
  time.sleep(.8)
  host.kill();host.wait(timeout=8)
  self.wait_for(lambda:not any(self.alive(pid) for pid in self.pids),seconds=2)
 def test_child_is_created_without_a_console_window(self):
  import native_process_host as module
  class Child:
   def __init__(self):
    from io import BytesIO
    self._handle=0;self.stdin=BytesIO()
   def poll(self):return 7
   def wait(self,**kwargs):return 7
  with patch.object(module.sys,'argv',['native_process_host.py','--','python','fixture.py']),patch.object(module.subprocess,'Popen',return_value=Child()) as launch,patch.object(module,'job_for',return_value=None),patch.object(module.threading.Thread,'start'):
   self.assertEqual(module.main(),7)
  self.assertTrue(launch.call_args.kwargs['creationflags'] & subprocess.CREATE_NO_WINDOW)

if __name__=='__main__':unittest.main()




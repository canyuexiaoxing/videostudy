"""Exercise downloader via local HTTP only; never installs or uploads."""
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
import threading,subprocess,tempfile,json,time
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'.local/qa/online-installer';DATA=bytes(i%251 for i in range(200000));COUNTS={};EVENTS=[]
class H(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  path=self.path.lstrip('/');count=COUNTS.get(path,0);COUNTS[path]=count+1;raw=self.headers.get('Range');offset=int(raw.split('=')[1].split('-')[0]) if raw else 0;EVENTS.append({'path':path,'offset':offset})
  if path=='missing':self.send_error(404);return
  if path=='redirect':self.send_response(302);self.send_header('Location','https://example.invalid/file');self.end_headers();return
  if path=='ignore-range':offset=0
  payload=(b'x'*len(DATA)) if path=='wrong' else DATA
  self.send_response(206 if offset else 200);self.send_header('Content-Length',str(len(payload)-offset))
  if offset:self.send_header('Content-Range',f'bytes {offset+1 if path=="bad-range-once" and count==0 else offset}-{len(DATA)-1}/{len(DATA)}')
  self.end_headers()
  try:
   if path=='interrupt-once' and count==0:self.wfile.write(payload[offset:offset+65000]);self.wfile.flush();self.close_connection=True;return
   if path=='slow':
    for start in range(offset,len(payload),4096):self.wfile.write(payload[start:start+4096]);self.wfile.flush();time.sleep(.01)
   else:self.wfile.write(payload[offset:])
  except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
server=ThreadingHTTPServer(('127.0.0.1',0),H);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();started=time.monotonic()
try:
 compile=subprocess.run(['C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe','/nologo','/target:exe','/out:'+str(OUT/'download-tests.exe'),str(ROOT/'desktop/installer/OnlineDownload.cs'),str(ROOT/'desktop/installer/OnlineDownload.test.cs')],capture_output=True,text=True);assert compile.returncode==0,compile.stdout
 with tempfile.TemporaryDirectory(prefix='framewise-download-') as tmp:
  result=subprocess.run([str(OUT/'download-tests.exe'),f'http://127.0.0.1:{server.server_port}/',tmp],capture_output=True,text=True,timeout=100)
  print(result.stdout);print(result.stderr);assert result.returncode==0
 assert any(x['path']=='file' and x['offset']==50000 for x in EVENTS)
 assert any(x['path']=='interrupt-once' and x['offset']>0 for x in EVENTS)
 (OUT/'download-tests.json').write_text(json.dumps({'passed':True,'checks':13,'events':EVENTS,'elapsedSeconds':round(time.monotonic()-started,3),'paidCalls':0,'installed':False},indent=2))
finally:server.shutdown();server.server_close()

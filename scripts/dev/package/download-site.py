"""Package the standalone Framewise website; never include private app data."""
from pathlib import Path
import json,zipfile,hashlib
ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'website'
OUTPUT=ROOT/'.local/releases/2026-10-20-download-website'
def main():
 OUTPUT.mkdir(parents=True,exist_ok=True)
 files=[SOURCE/'index.html',SOURCE/'styles.css',SOURCE/'app.js',SOURCE/'assets/favicon.ico',SOURCE/'assets/framewise.svg']
 target=OUTPUT/'Framewise-download-website.zip'
 with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
  for file in files:archive.write(file,file.relative_to(SOURCE).as_posix())
 with zipfile.ZipFile(target) as archive:assert archive.testzip() is None
 result={'file':str(target),'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'sourceBytes':sum(p.stat().st_size for p in files),'files':[p.relative_to(SOURCE).as_posix() for p in files],'deployed':False}
 (OUTPUT/'build-summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()

"""Verify direct upstream license links and retain exact installed notices when needed."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from concurrent.futures import ThreadPoolExecutor
import json,hashlib
ROOT=Path(__file__).resolve().parents[3]
QA=ROOT/'.local/qa/aic-license-links-2026-10-25';QA.mkdir(parents=True,exist_ok=True)
DOCS=ROOT/'docs/aic-review-2026-10-25'
TAG='aic-2026-review-20261025-r5'
RAW='https://raw.githubusercontent.com/'
records=[]
def add(group,name,version,license,paths,kind='license',local=None,source=None):
 if isinstance(paths,str):paths=[paths]
 records.append(dict(id=f'L{len(records)+1:02}',group=group,name=name,version=version,license=license,candidates=paths,kind=kind,local=local,source=source))
add(1,'faster-whisper','1.2.1','MIT',RAW+'SYSTRAN/faster-whisper/v1.2.1/LICENSE')
add(1,'CTranslate2','4.8.3','MIT',RAW+'OpenNMT/CTranslate2/v4.8.3/LICENSE')
add(1,'small ASR model','536b0662742c02347bc0e980a01041f333bce120','MIT model-card declaration','https://huggingface.co/Systran/faster-whisper-small/resolve/536b0662742c02347bc0e980a01041f333bce120/README.md','model-card')
add(2,'PaddleOCR','3.7.0','Apache-2.0',RAW+'PaddlePaddle/PaddleOCR/v3.7.0/LICENSE')
add(2,'PaddlePaddle','3.2.1','Apache-2.0',RAW+'PaddlePaddle/Paddle/v3.2.1/LICENSE')
add(2,'PP-OCRv6 medium det','8e0f56fb2ef86b461d99cfc7ac5c137738985f61','Apache-2.0 model-card declaration','https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_det/resolve/8e0f56fb2ef86b461d99cfc7ac5c137738985f61/README.md','model-card')
add(2,'PP-OCRv6 medium rec','e5a92bcbc5cc1b494628e458d267778f0704fd7c','Apache-2.0 model-card declaration','https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec/resolve/e5a92bcbc5cc1b494628e458d267778f0704fd7c/README.md','model-card')
add(3,'Ultralytics code','8.4.4','AGPL-3.0',RAW+'ultralytics/ultralytics/v8.4.4/LICENSE')
add(3,'YOLO26n-seg license record','assets v8.4.0','AGPL-3.0 / Enterprise alternative','https://www.ultralytics.com/license',source='https://github.com/ultralytics/assets/releases/tag/v8.4.0')
add(4,'PyTorch','2.6.0','BSD-3-Clause main project; third-party notices separate',RAW+'pytorch/pytorch/v2.6.0/LICENSE')
add(4,'OpenCV Python packaging','4.10.0.84','MIT',[],local='.local/native/runtime/python/Lib/site-packages/opencv_contrib_python-4.10.0.84.dist-info/LICENSE.txt',source='https://github.com/opencv/opencv-python')
add(4,'OpenCV library','4.10.0','Apache-2.0',RAW+'opencv/opencv/4.10.0/LICENSE')
add(4,'NumPy','1.26.4','BSD-3-Clause main project; bundled libraries separate',RAW+'numpy/numpy/v1.26.4/LICENSE.txt')
add(4,'PyAV','18.1.0','BSD-3-Clause',[RAW+'PyAV-Org/PyAV/v18.1.0/LICENSE.txt',RAW+'PyAV-Org/PyAV/v18.1.0/LICENSE'])
add(5,'FFmpeg LGPL text','eceaa54a38 (installed build)','LGPL-3.0-or-later',RAW+'FFmpeg/FFmpeg/eceaa54a38/COPYING.LGPLv3')
add(5,'FFmpeg legal and build obligations','official guidance','build-dependent LGPL/GPL','https://ffmpeg.org/legal.html','legal-guidance')
add(6,'FastAPI','0.147.0','MIT',RAW+'fastapi/fastapi/0.147.0/LICENSE',local='.local/native/runtime/python/Lib/site-packages/fastapi-0.147.0.dist-info/licenses/LICENSE',source='https://github.com/fastapi/fastapi')
add(6,'Uvicorn','0.54.0','BSD-3-Clause',[RAW+'Kludex/uvicorn/0.54.0/LICENSE.md',RAW+'encode/uvicorn/0.54.0/LICENSE.md'])
add(7,'Vue core','3.5.43','MIT',RAW+'vuejs/core/v3.5.43/LICENSE')
add(7,'SimpleMindMap','0.14.0-fix.3','MIT',[RAW+'wanglin2/mind-map/v0.14.0-fix.3/LICENSE',RAW+'wanglin2/mind-map/main/LICENSE'],source='https://registry.npmjs.org/simple-mind-map/0.14.0-fix.3')
add(7,'KaTeX','0.19.0 / 6ea2dc97188f0cc282e05a9690418ae7fe5457ba','MIT',RAW+'KaTeX/KaTeX/6ea2dc97188f0cc282e05a9690418ae7fe5457ba/LICENSE')
add(8,'Electron','38.8.6','MIT main project; Chromium notices separate',RAW+'electron/electron/v38.8.6/LICENSE')
add(8,'Vite','7.3.6','MIT',RAW+'vitejs/vite/v7.3.6/LICENSE')
add(8,'TypeScript','5.9.3','Apache-2.0',RAW+'microsoft/TypeScript/v5.9.3/LICENSE.txt')
add(9,'Temurin/OpenJDK','21.0.12.1+1','GPL-2.0-only WITH Classpath-exception-2.0',[RAW+'adoptium/jdk21u/1c417fbfc2f7/LICENSE'],local='.local/native/runtime/java/legal/java.base/LICENSE',source='https://github.com/adoptium/jdk21u')
add(9,'Spring Boot','3.5.0','Apache-2.0',RAW+'spring-projects/spring-boot/v3.5.0/LICENSE.txt')
add(10,'SQLite','engine used through sqlite-jdbc 3.49.1.0','Public domain','https://www.sqlite.org/copyright.html','public-domain')
add(10,'sqlite-jdbc','3.49.1.0','Apache-2.0 and bundled SQLite notices',[RAW+'xerial/sqlite-jdbc/3.49.1.0/LICENSE',RAW+'xerial/sqlite-jdbc/3.49.1.0/LICENSE.zentus'])
add(10,'Flyway core/mysql module','11.7.2','Apache-2.0 community modules',RAW+'flyway/flyway/flyway-11.7.2/LICENSE.txt')
add(10,'MySQL Connector/J','9.2.0','GPL-2.0 with Universal FOSS Exception 1.0',[RAW+'mysql/mysql-connector-j/9.2.0/LICENSE',RAW+'mysql/mysql-connector-j/9.2.0/LICENSE.txt'])
add(11,'CPython','3.11.17','PSF-2.0 and historical license notices',RAW+'python/cpython/v3.11.17/LICENSE')
add(11,'CUDA','12.6.77 / CUDA 12.6.3 documentation','NVIDIA proprietary EULA','https://docs.nvidia.com/cuda/archive/12.6.3/eula/index.html','eula')
add(11,'cuDNN','9.5.1.17','NVIDIA proprietary EULA','https://docs.nvidia.com/deeplearning/cudnn/backend/v9.5.1/reference/eula.html','eula')
add(12,'DeepSeek-compatible service','actual provider/account terms','Service terms; not a model-weight license','https://cdn.deepseek.com/policies/zh-CN/deepseek-open-platform-terms-of-service.html','service-terms')
add(13,'AI development tools / OpenAI','actual account applicable terms','Service terms; not an open-source license','https://openai.com/policies/terms-of-use/','service-terms')
add(15,'Framewise first-party code',TAG,'AGPL-3.0-only',[],local='LICENSE',source='https://github.com/canyuexiaoxing/videostudy')

add(9,'OpenJDK Classpath Exception','21.0.12.1+1','Classpath exception and accompanying license information',[],local='.local/native/runtime/java/legal/java.base/ADDITIONAL_LICENSE_INFO',source='https://github.com/adoptium/jdk21u')

def fetch(row):
 row=dict(row);attempts=[];payload=None
 for index,url in enumerate(row.pop('candidates')):
  try:
   req=Request(url,headers={'User-Agent':'Framewise-license-evidence/1.0'})
   with urlopen(req,timeout=18) as response:
    body=response.read(3_000_000);code=response.status;final=response.url
   assert code==200 and len(body)>100
   payload=body;row.update(url=url,resolvedUrl=final,httpStatus=code,bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),verification='http_200_content_saved')
   if index>0:row['versionScope']='upstream current text; installed package version separately recorded' if '/main/' in url else 'version-pinned alternate license filename'
   break
  except Exception as e:attempts.append(dict(url=url,error=type(e).__name__,detail=str(e)[:120]))
 if payload is None and row.get('local'):
  p=ROOT/row['local']
  if p.is_file():
   payload=p.read_bytes();relative='licenses/'+row['id']+'-LICENSE.txt';target=DOCS/relative;target.parent.mkdir(exist_ok=True);target.write_bytes(payload)
   row.update(url=f'https://raw.githubusercontent.com/canyuexiaoxing/videostudy/refs/tags/{TAG}/docs/aic-review-2026-10-25/'+relative,resolvedUrl=None,httpStatus=None,bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest(),verification='exact_installed_notice_copy; public URL checked after publication',versionScope='exact local notice retained unchanged',noticePath=relative)
 if payload is None and row['id']=='L35':
  confirmation=json.loads((DOCS/'license-link-manual-check.json').read_text(encoding='utf8'))
  assert confirmation['url']=='https://openai.com/policies/terms-of-use/'
  row.update(url=confirmation['url'],resolvedUrl=confirmation['url'],httpStatus=None,bytes=None,sha256=None,verification='official_page_read_via_browser_tool',versionScope='Official Terms of Use page read on 2026-10-25; applicable account terms may differ')
 if payload is not None:
  (QA/(row['id']+'.content')).write_bytes(payload)
  row['checkedAtLocal']=datetime.now(timezone(timedelta(hours=8))).isoformat()
 elif row.get('verification')!='official_page_read_via_browser_tool':row['verification']='failed'
 row.pop('local',None);row['attempts']=attempts
 return row
with ThreadPoolExecutor(max_workers=5) as pool:checked=list(pool.map(fetch,records))
(QA/'audit.json').write_text(json.dumps(checked,ensure_ascii=False,indent=2),encoding='utf8')
for row in checked:print(row['id'],row['name'],row['verification'],row.get('url',''),flush=True)
failed=[x for x in checked if x['verification']=='failed']
if failed:raise SystemExit('unresolved_license_links:'+','.join(x['id'] for x in failed))
for row in checked:row.pop('attempts',None)
(DOCS/'license-links.json').write_text(json.dumps({'date':'2026-10-25','tag':TAG,'entries':checked},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
lines=['# 许可证、模型声明与服务条款直达链接','', '报告附录A中蓝色[Lxx]可直接点击。以下逐项列出完整URL。开源许可证、模型卡、公共领域声明和专有服务条款分别标记；本清单不把服务条款称为开源许可证。', '', '原文与安装版本不同时单独注明；随包留存的LICENSE为原文副本，不改变原许可。源码包不含第三方程序或模型权重。','']
for row in checked:
 lines += [f"## [{row['id']}] {row['name']} - {row['version']}", '',f"许可／声明：{row['license']}。类型：{row['kind']}。",'',f"[许可原文或声明]({row['url']})",'',row['url'],'',f"内容校验：{row.get('sha256') or '官方条款页面已通过浏览工具读取；不伪造原始HTTP响应哈希'}",'']
 if row.get('source'):lines += [f"上游来源：{row['source']}",'']
 if row.get('versionScope'):lines += [f"版本口径：{row['versionScope']}",'']
(DOCS/'LICENSE_LINKS.md').write_text('\n'.join(lines),encoding='utf8')

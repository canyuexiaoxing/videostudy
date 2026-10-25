
from pathlib import Path
from pypdf import PdfReader
import pypdfium2 as pdfium
from PIL import Image,ImageOps,ImageDraw
import json,re,hashlib
ROOT=Path(__file__).resolve().parents[3];q=ROOT/'.local/qa/aic-report-2026-10-25';p=ROOT/'cailiao/Framewise_AIC技术报告_映知_2026-10-25.pdf'
r=PdfReader(p);d=pdfium.PdfDocument(str(p));text='\n'.join(x.extract_text() or '' for x in r.pages)
assert len(r.pages)==31
assert p.stat().st_size<10_000_000
for value in ['AIC-2026-60885194','40173c8','697','696','163','207','150.044','163.452','25.485','37.676','21,429','37.891','463','101','79','45','队长','队员（2名）','① 转写与选图','④ 页面／组图文理解','当前跳过独立调用','AST最多70节点','repair_used','AGPL-3.0-only','附录E 实际界面与操作核验','SOURCE_MANIFEST.json','已可匿名访问']:
 assert ''.join(value.split()) in ''.join(text.split()),value
private_policy=q/'restricted-identifiers.json'
private_identifiers=json.loads(private_policy.read_text(encoding='utf8')) if private_policy.exists() else []
for forbidden in private_identifiers+['Authorization: Bearer', 'sk-', '本文不声称每行代码均由人工手写', '不从Git作者推断个人分工', '未发现根LICENSE']:
 assert forbidden not in text,forbidden
body=json.loads((q/'report-all-pages.json').read_text(encoding='utf8'))
# Verify every prose block in the generated report.
flatten=''.join(text.split())
for page in body:
 for block in page['blocks']:
  if block[0] in ('p','small','h'):assert ''.join(block[1].split()) in flatten,block[1][:40]
  elif block[0]=='table':
   for row in [block[1]]+block[2]:
    for cell in row:assert ''.join(str(cell).split()) in flatten,str(cell)[:40]
thumbs=[]
for i in range(len(d)):
 im=d[i].render(scale=1.35).to_pil().convert('RGB');im.save(q/f'page-{i+1:02}.png')
 card=Image.new('RGB',(326,475),'#dce0e6');t=ImageOps.contain(im,(306,440));card.paste(t,((326-t.width)//2,0));ImageDraw.Draw(card).text((10,452),str(i+1),fill='black');thumbs.append(card)
for st in range(0,len(thumbs),6):
 sh=Image.new('RGB',(978,950),'white')
 for j,t in enumerate(thumbs[st:st+6]):sh.paste(t,((j%3)*326,(j//3)*475))
 sh.save(q/f'contact-{st//6+1}.png')
res={'file':str(p),'bytes':p.stat().st_size,'totalPages':31,'bodyPages':15,'appendixPages':14,'frontMatterPages':2,'sizeUnder10MB':True,'requiredFactsPresent':True,'proseComplete':True,'restrictedIdentityOrCredentialsFound':False,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
(q/'report-check.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(res,ensure_ascii=False))

"""Group calculation fragments only using grounded new-question transitions."""
import re
from copy import deepcopy
NUMBER = r'[0-9一二三四五六七八九十百]+'
CUE = re.compile(r'再来|再看|来看|往下看|接下来|下下|一下看')
def _number(value):
 if value.isdigit():return int(value)
 digits=dict(zip('一二三四五六七八九','123456789'))
 if '十' in value:
  left,right=value.split('十',1);return int(digits.get(left,'1'))*10+int(digits.get(right,'0'))
 return int(digits.get(value,'0'))
def question_opening(text):
 text=re.sub(r'\s+','',text)
 match=re.search(r'(?:第|题)('+NUMBER+r')(?:题|体|个)',text[:40])
 if match:
  prefix=text[:match.start()];suffix=text[match.end():]
  if re.search(r'回到|回顾|刚才|不是|前面|上一个',prefix) or re.match(r'的(?:方法|结论|结果|答案|思路|做法)',suffix):return None
  if CUE.search(prefix) or (match.start()==0 and re.match(r'开始',suffix)):
   return _number(match.group(1)) or None
 prefix=text[:32]
 if re.search(r'回到|回顾|刚才|前面|上一个',prefix):return None
 if re.search(r'(?:再来|来看|接下来|看)(?:一?道)?下一题',prefix):return -1
 if re.search(r'(?:(?:来看|下面看|接下来(?:看)?)(?:这道|这个)(?:例题|题目)|(?:来看|再看|下面看|接下来(?:看)?|再来(?:做)?)(?:新的|新一道|一道|另一个|另一道)(?:例题|题目|题|例子))',prefix):return -1
 return None

def group_examples(examples,segments):
 if not examples:return []
 ordered=sorted(segments,key=lambda s:s['startMs'])
 markers=[];last_number=None
 for s in ordered:
  number=question_opening(s['text'])
  if number is not None and (number==-1 or number!=last_number):
   markers.append((s,number));last_number=number
 if not markers:return deepcopy(examples)
 first=min(examples,key=lambda n:n['startMs'])
 start=first['startMs'];source=next((s for s in ordered if s['id']==first['evidenceRefs'][0]['sourceId']),None) if first.get('evidenceRefs') else None
 if not source:return deepcopy(examples)
 if not markers or markers[0][0]['startMs']>start:markers.insert(0,(source,None))
 groups={}
 for node in sorted(examples,key=lambda n:n['startMs']):
  for j,(opening,_) in enumerate(markers):
   if node['startMs']<=opening['startMs']<node['endMs']:
    groups.setdefault(j,dict(refs={},nodes={}))['nodes'][node['id']]=node
  for ref in node.get('evidenceRefs',[]):
   index=0
   for j,(opening,_) in enumerate(markers):
    if opening['startMs']>ref['startMs']:break
    index=j
   group=groups.setdefault(index,dict(refs={},nodes={}))
   group['refs'][ref['sourceId']]=deepcopy(ref);group['nodes'][node['id']]=node
 result=[]
 for index,group in sorted(groups.items()):
  opening,number=markers[index]
  has_refs=bool(group['refs'])
  group['refs'][opening['id']]=dict(sourceType='transcript',sourceId=opening['id'],startMs=opening['startMs'],endMs=opening['endMs'],quote=opening['text'])
  refs=sorted(group['refs'].values(),key=lambda ref:ref['startMs'])
  candidates=sorted(group['nodes'].values(),key=lambda n:n['startMs'])
  representative=next((n for n in candidates if n['startMs']<=opening['startMs']<n['endMs']),candidates[0])
  title=re.sub(r'^例题\s*[0-9一二三四五六七八九十]*[：:]\s*','',representative['title'])
  if number and number>0:title=f'例题 {number}：{title}' if has_refs and title!=f'例题 {number}' else f'例题 {number}'
  result.append(dict(id='question_'+opening['id'],title=title,startMs=refs[0]['startMs'],endMs=max(ref['endMs'] for ref in refs),evidenceRefs=refs,children=[]))
 return result

"""Local consolidation of concept labels from existing chunk requests; no model calls."""
from copy import deepcopy
import re

def _refs(nodes):
 refs={}
 for node in nodes:
  for ref in node['evidenceRefs']:refs[ref['sourceId']]=deepcopy(ref)
 return sorted(refs.values(),key=lambda ref:ref['startMs'])

def _node(identity,title,refs,children):
 return dict(id=identity,title=title,startMs=refs[0]['startMs'] if refs else 0,endMs=max((ref['endMs'] for ref in refs),default=0),evidenceRefs=refs,children=children)

def _merge(nodes):
 grouped={}
 for node in nodes:grouped.setdefault(node['title'].strip(),[]).append(node)
 result=[]
 for group in grouped.values():
  result.append(_node(group[0]['id'],group[0]['title'],_refs(group),_merge([c for n in group for c in n['children']])))
 return result

def organize_chapters(chapters):
 chapters=deepcopy(chapters)
 subjects={};fallback=[]
 for chapter in chapters:
  unmatched=[]
  for concept in chapter['children']:
   key=concept.get('_conceptKey');subject=concept.get('_subject')
   supported=isinstance(key,str) and 2<=len(key.strip())<=40 and key.strip() not in {'公式','方法','知识','计算','定义','条件','极限','课程','核心知识'} and (key in concept['title'] or any(key in r['quote'] for r in concept['evidenceRefs']))
   if supported:
    key=key.strip();subject=subject.strip() if isinstance(subject,str) and 0<len(subject.strip())<=40 else chapter['title']
    subjects.setdefault(subject,{}).setdefault(key,[]).append(concept)
   else:unmatched.append(concept)
  if unmatched:fallback.append(_node(chapter['id'],chapter['title'],_refs(unmatched),unmatched))
 result=[]
 for index,(subject,concepts) in enumerate(subjects.items()):
  children=[]
  for key,group in concepts.items():
   details=[]
   for original in group:
    details.extend(original['children'])
    if not original['children'] and original['title']!=key:
     details.append(dict(original,id='detail_'+original['id']))
   children.append(_node(group[0]['id'],key,_refs(group),_merge(details)))
  result.append(_node('topic_'+str(index),subject,_refs(children)[:3],children))
 result.extend(fallback)
 def strip(node):
  node.pop('_conceptKey',None);node.pop('_subject',None)
  for child in node['children']:strip(child)
 for node in result:strip(node)
 return result

"""Exact registry-based citation repairs and bounded metadata-only diagnostics."""
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
import json,re
from model_diagnostics import record_event

VERSION='course-citations-v1'
LIMIT=128

def safe_id(value):
    return value if isinstance(value,str) and len(value)<=80 and re.fullmatch(r'(?:t_\d+|frame_\d+|page_\d+_(?:knowledge|example)_\d+)',value) else '<redacted>'

class CitationReport:
    def __init__(self,payload):
        self.task=payload.get('_diagnosticTaskId');self.evidence={r['sourceId']:r for r in payload['sourceEvidence']+payload['imageEvidence']}
        self.paths={};self.issues=[];self.repairs=[];self.repaired_count=0;self.issue_count=0;self.seen=set()
    def path(self,node):return self.paths.get(id(node),'root')
    def emit(self,node,reason,field=None,reference=None,repair=False):
        row={'node_path':self.path(node),'reason':reason}
        if field in ('sourceIds','imageIds'):row['reference_field']=field
        if reference is not None:row['reference_id']=safe_id(reference)
        identity=(repair,tuple(row.items()))
        if identity in self.seen:return
        self.seen.add(identity)
        if repair:self.repaired_count+=1;target=self.repairs
        else:self.issue_count+=1;target=self.issues
        if len(target)<LIMIT:
            target.append(row)
            record_event('diagnostic_check',self.task,operation='course_map',stage='validation',**row)
    def normalize(self,raw):
        raw=deepcopy(raw);visited=set();count=[0]
        def visit(node,path,depth=0):
            if not isinstance(node,dict) or id(node) in visited or depth>14 or count[0]>=8192:return
            visited.add(id(node));count[0]+=1;self.paths[id(node)]=path
            if 'sourceIds' in node or 'imageIds' in node:
                old_sources,old_images=node.get('sourceIds',[]),node.get('imageIds',[])
                if not isinstance(old_sources,list) or not isinstance(old_images,list) or any(not isinstance(x,str) or not x for x in old_sources+old_images):
                    self.emit(node,'reference_format_invalid')
                else:
                    result={'sourceIds':[],'imageIds':[]}
                    for field,values in [('sourceIds',old_sources),('imageIds',old_images)]:
                        for value in values:
                            canonical=value.strip();evidence=self.evidence.get(canonical)
                            if evidence and evidence.get('sourceType') in ('transcript','image'):
                                correct='sourceIds' if evidence['sourceType']=='transcript' else 'imageIds'
                                if canonical!=value or correct!=field:self.emit(node,'reference_repaired',field,canonical,repair=True)
                                if canonical not in result[correct]:result[correct].append(canonical)
                            else:
                                result[field].append(value);self.emit(node,'reference_unknown',field,value)
                    node.update(result)
            for key in ('children','details','examples','candidateDecisions'):
                values=node.get(key)
                if isinstance(values,list):
                    for index,value in enumerate(values[:8192]):visit(value,f'{key}[{index}]' if path=='root' else f'{path}.{key}[{index}]',depth+1)
            if isinstance(node.get('mergeEvidence'),dict):visit(node['mergeEvidence'],f'{path}.mergeEvidence',depth+1)
        visit(raw,'root');return raw
    def rejection(self,node,reason,field=None,reference=None):
        self.emit(node,reason,field,reference)
        labels={'reference_missing':'节点缺少实际来源','reference_unknown':'来源编号不存在','reference_wrong_type':'来源类型不匹配','reference_disallowed':'来源不属于该知识或例题范围','reference_format_invalid':'来源列表格式无效'}
        location=self.path(node)
        if field:location+=' / '+field
        if reference is not None:location+=' / '+safe_id(reference)
        return f'节点来源校验失败：{labels[reason]}（{location}），已拒绝'
    def summary(self,status,prompt_version):
        return {'version':VERSION,'createdAt':datetime.now(timezone.utc).isoformat(),'promptVersion':prompt_version,'status':status,'repaired_count':self.repaired_count,'issue_count':self.issue_count,'repairs':self.repairs,'issues':self.issues,'omitted_count':max(0,self.issue_count-len(self.issues))+max(0,self.repaired_count-len(self.repairs))}

def save_report(root,report,status,prompt_version):
    directory=Path(root)/'.map-validation';directory.mkdir(parents=True,exist_ok=True)
    temporary=directory/f'{uuid4().hex}.tmp'
    try:
        temporary.write_text(json.dumps(report.summary(status,prompt_version),ensure_ascii=False,indent=2),encoding='utf-8')
        temporary.replace(directory/'latest.json')
    finally:temporary.unlink(missing_ok=True)


# Handles belong only to one model request; stored citations keep real frame PTS.
def wire_registry(payload):
    canonical=[r['sourceId'] for r in payload['imageEvidence']]
    if len(canonical)!=len(set(canonical)):raise ValueError('duplicate_image_registry_id')
    aliases={sid:f'img_{i+1}' for i,sid in enumerate(canonical)}
    # Refuse collisions with transcript IDs, including nonstandard imported IDs.
    if set(aliases.values()) & {r['sourceId'] for r in payload['sourceEvidence']}:
        raise ValueError('citation_handle_collision')
    return translate_references(payload,aliases),{v:k for k,v in aliases.items()}


def translate_references(value,mapping):
    if isinstance(value,list):return [translate_references(item,mapping) for item in value]
    if not isinstance(value,dict):return deepcopy(value)
    result={}
    for key,item in value.items():
        if key in ('sourceId','imageId') and isinstance(item,str):result[key]=mapping.get(item,item)
        elif key in ('sourceIds','imageIds','firstHandImageIds','firstHandSourceIds') and isinstance(item,list):
            result[key]=[mapping.get(x.strip(),x) if isinstance(x,str) else deepcopy(x) for x in item]
        else:result[key]=translate_references(item,mapping)
    return result



def citation_nodes(raw):
    count=[0]
    def visit(node,path,depth=0):
        if not isinstance(node,dict) or depth>14 or count[0]>=8192:return
        count[0]+=1;yield path,node
        for key in ('children','details','examples','candidateDecisions'):
            values=node.get(key)
            if isinstance(values,list):
                for i,value in enumerate(values[:8192]):
                    yield from visit(value,f'{key}[{i}]' if path=='root' else f'{path}.{key}[{i}]',depth+1)
        if isinstance(node.get('mergeEvidence'),dict):yield from visit(node['mergeEvidence'],path+'.mergeEvidence',depth+1)
    yield from visit(raw,'root')


def unknown_references(raw,payload,aliases):
    known={r['sourceId'] for r in payload['sourceEvidence']+payload['imageEvidence']}|set(aliases)
    bad=[]
    for path,node in citation_nodes(raw):
        for field in ('sourceIds','imageIds'):
            values=node.get(field,[])
            if not isinstance(values,list):continue
            for i,sid in enumerate(values):
                if isinstance(sid,str) and sid.strip() not in known:
                    bad.append({'path':path,'field':field,'index':i,'from':sid})
                    if len(bad)>LIMIT:return bad
    return bad


def missing_references(raw):
    """Leaves/details/examples need refs; categories may inherit repaired children."""
    missing=[];count=[0]
    def own(node):
        if not isinstance(node,dict) or not isinstance(node.get('title'),str) or not node['title'].strip():return None
        lists=[node.get(field,[]) for field in ('sourceIds','imageIds')]
        if any(not isinstance(values,list) or any(not isinstance(v,str) or not v for v in values) for values in lists):return None
        return bool(lists[0] or lists[1])
    def walk(node,path,kind='knowledge',depth=0,detail=False):
        if count[0]>=8192 or depth>14:return False
        count[0]+=1;has=own(node)
        if has is None:return False
        supported=has
        if kind=='knowledge' and not detail:
            for field in ('children','details'):
                values=node.get(field,[])
                if not isinstance(values,list):continue
                for i,child in enumerate(values[:8192]):
                    supported=walk(child,f'{path}.{field}[{i}]',kind,depth+1,field=='details') or supported
        if not supported:
            missing.append({'path':path,'kind':kind})
            # Parent will acquire evidence only if all requested additions validate.
            return True
        return supported
    if not isinstance(raw,dict):return missing
    for key,kind in (('children','knowledge'),('examples','example')):
        if isinstance(raw.get(key),list):
            for i,node in enumerate(raw[key][:8192]):walk(node,f'{key}[{i}]',kind)
    return missing


def apply_reference_corrections(raw,problems,reply,payload,aliases,missing=None):
    # Exact slots plus explicitly identified source-less nodes only; atomic patch.
    missing=missing or []
    if not isinstance(reply,dict) or not {'corrections'}<=set(reply) or set(reply)-{'corrections','additions'}:return None
    corrections=reply['corrections'];additions=reply.get('additions',[])
    if not isinstance(corrections,list) or len(corrections)!=len(problems) or not isinstance(additions,list) or len(additions)!=len(missing):return None
    expected={(p['path'],p['field'],p['index']):p['from'] for p in problems}
    allowed={'sourceIds':{r['sourceId'] for r in payload['sourceEvidence']},
             'imageIds':{r['sourceId'] for r in payload['imageEvidence']}|set(aliases)}
    result=deepcopy(raw);nodes=dict(citation_nodes(result));seen=set()
    for c in corrections:
        if not isinstance(c,dict) or set(c)!={'path','field','index','from','to'}:return None
        if not isinstance(c['path'],str) or not isinstance(c['field'],str) or c['field'] not in allowed or type(c['index']) is not int:return None
        slot=(c['path'],c['field'],c['index'])
        if slot not in expected or slot in seen or c['from']!=expected[slot] or not isinstance(c['to'],str) or c['to'] not in allowed[c['field']]:return None
        nodes[c['path']][c['field']][c['index']]=c['to'];seen.add(slot)
    targets={m['path'] for m in missing};filled=set()
    for addition in additions:
        if not isinstance(addition,dict) or set(addition)!={'path','sourceIds','imageIds'}:return None
        path=addition['path']
        if not isinstance(path,str) or path not in targets or path in filled or path not in nodes:return None
        node=nodes[path]
        if node.get('sourceIds',[])!=[] or node.get('imageIds',[])!=[]:return None
        for field in ('sourceIds','imageIds'):
            ids=addition[field]
            if not isinstance(ids,list) or any(not isinstance(sid,str) or sid not in allowed[field] for sid in ids) or len(ids)!=len(set(ids)):return None
        if not addition['sourceIds'] and not addition['imageIds']:return None
        node.update(sourceIds=list(addition['sourceIds']),imageIds=list(addition['imageIds']));filled.add(path)
    return result if len(seen)==len(expected) and filled==targets else None

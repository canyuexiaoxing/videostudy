"""Local map context snapshots, bound to the saved map and immutable source images."""
import base64,hashlib,json,os
from pathlib import Path
from uuid import uuid4
from ignored_region import normalize_setting,prepare_image

def map_fingerprint(result):
    def node(n):
        n=n or {}
        return {k:n.get(k) for k in ('id','title','startMs','endMs')} | {'evidenceRefs':n.get('evidenceRefs') or [],'children':[node(c) for c in n.get('children') or []],'details':[node(c) for c in n.get('details') or []]}
    value={'promptVersion':result.get('promptVersion'),'createdAt':result.get('createdAt'),'modelId':result.get('modelId'),'root':node(result.get('root')),'examples':[node(n) for n in result.get('examples') or []]}
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def image_record(root,ms,setting=None,expected_sha=None):
    if type(ms) is not int or ms<0:raise ValueError('practice_images_invalid')
    root=Path(root).resolve();path=root/f'{ms}.jpg'
    if path.resolve().parent!=root or not path.is_file():raise ValueError('practice_images_missing')
    raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest()
    if expected_sha and digest!=expected_sha:raise ValueError('practice_map_context_changed')
    import cv2
    image=cv2.imread(str(path))
    if image is None:raise ValueError('practice_images_missing')
    setting=normalize_setting(setting)
    if setting:
        ok,encoded=cv2.imencode('.jpg',prepare_image(image,setting,ms))
        if not ok:raise ValueError('practice_images_invalid')
        raw=encoded.tobytes()
    return {'frameTimeMs':ms,'imageId':f'frame_{ms}','sha256':digest,'region':setting,'_bytes':raw}

def image_content(images,*,dedup=True):
    grouped={}
    for index,item in enumerate(images):
        digest=hashlib.sha256(item['_bytes']).hexdigest() if dedup else str(index)
        group=grouped.setdefault(digest,{'ids':[],'bytes':item['_bytes']})
        group['ids'].append(item['imageId'])
    content=[]
    for group in grouped.values():
        caption=('imageIds='+','.join(group['ids']) if dedup else 'imageId='+group['ids'][0]+'; detail=original')
        content.extend([{'type':'text','text':caption},{'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(group['bytes']).decode(),'detail':'original'}}])
    return content

def save_map_conversation(root,payload,images,reply,result,system_text,*,expected_hashes=None):
    if result.get('status')!='completed':return
    root=Path(root);fingerprint=map_fingerprint(result)
    records=[image_record(root,ms,payload.get('_visualRegionsByFrame',{}).get(str(ms)),(expected_hashes or {}).get(f'frame_{ms}')) for ms,_,_ in images]
    value={'version':1,'mapFingerprint':fingerprint,'systemText':system_text,
        'userText':json.dumps({k:v for k,v in payload.items() if not k.startswith('_')},ensure_ascii=False),
        'assistantText':json.dumps(reply,ensure_ascii=False),'modelId':os.environ.get('DEEPSEEK_MODEL','deepseek-flash'),
        'images':[{k:v for k,v in r.items() if not k.startswith('_')} for r in records]}
    directory=root/'.map-context';directory.mkdir(parents=True,exist_ok=True)
    temporary=directory/f'{uuid4().hex}.tmp'
    try:
        temporary.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
        temporary.replace(directory/f'{fingerprint}.json')
    finally:temporary.unlink(missing_ok=True)

def load_map_conversation(root,result):
    fingerprint=map_fingerprint(result);path=Path(root)/'.map-context'/f'{fingerprint}.json'
    try:value=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):raise ValueError('practice_map_context_missing') from None
    if value.get('version')!=1 or value.get('mapFingerprint')!=fingerprint:raise ValueError('practice_map_context_changed')
    if any(not isinstance(value.get(k),str) for k in ('systemText','userText','assistantText')) or not isinstance(value.get('images'),list):raise ValueError('practice_map_context_changed')
    value['_images']=[image_record(root,r['frameTimeMs'],r.get('region'),r['sha256']) for r in value['images']]
    return value

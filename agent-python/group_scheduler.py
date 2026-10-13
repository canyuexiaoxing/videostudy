"""Revision-aware streaming group scheduler. Provider calls are supplied by the caller."""
import hashlib,json,threading,time
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor,CancelledError


def _atomic(path,value):
 path.parent.mkdir(parents=True,exist_ok=True)
 temporary=path.with_name(path.name+'.'+uuid4().hex+'.tmp')
 try:temporary.write_text(json.dumps(value),encoding='utf-8');temporary.replace(path)
 finally:temporary.unlink(missing_ok=True)

def cancel_run(directory):
 directory=Path(directory)
 try:run=json.loads((directory/'active-run.json').read_text())['runId']
 except (OSError,ValueError,KeyError):run=None
 _atomic(directory/'cancel.json',dict(runId=run,cancelled=True))

def reset_run(directory):
 directory=Path(directory)
 # Invalidate old in-flight work even if it never observed the cancel marker.
 _atomic(directory/'active-run.json',dict(runId='reset_'+uuid4().hex))
 (directory/'cancel.json').unlink(missing_ok=True)

class RunSignal:
 def __init__(self,directory):
  self.directory=Path(directory);self.event=threading.Event();self.run_id=uuid4().hex
  if (self.directory/'cancel.json').exists():raise CancelledError('analysis_cancelled')
  _atomic(self.directory/'active-run.json',dict(runId=self.run_id))
 def is_set(self):
  if self.event.is_set():return True
  try:
   active=json.loads((self.directory/'active-run.json').read_text())['runId']
   if active!=self.run_id:self.event.set()
   if (self.directory/'cancel.json').exists():self.event.set()
  except (OSError,ValueError,KeyError):self.event.set()
  return self.event.is_set()
 def set(self):self.event.set()
 def check(self):
  if self.is_set():raise CancelledError('analysis_cancelled')

class ReadyGroupScheduler:
 def __init__(self,keyframe_dir,analyze,*,max_workers=5,initial_groups=4,checkpoint=None,progress=None,signal=None,max_supplements=2):
  if not 1<=max_workers<=5 or initial_groups<1 or not 0<=max_supplements<=2:raise ValueError('Invalid group scheduling limits')
  self.directory=Path(keyframe_dir);self.analyze=analyze;self.checkpoint=checkpoint;self.progress=progress
  self.signal=signal or threading.Event();self.max_supplements=max_supplements;self.initial_groups=initial_groups
  self.pool=ThreadPoolExecutor(max_workers=max_workers,thread_name_prefix='ready-group')
  self.lock=threading.RLock();self.changed=threading.Condition(self.lock)
  self.started=False;self.closed=False;self.pages=[];self.segments=[];self.visuals={}
  self.desired={};self.results={};self.inflight={};self.links={};self.image_hashes={};self.supplement_spent={}
 def _check(self):
  if self.signal.is_set():raise CancelledError('analysis_cancelled')
 def _hash(self,value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 def _images(self,page):
  result=[]
  for t in page.get('representativeFrameTimesMs',[]):
   path=self.directory/f'{t}.jpg'
   if t not in self.visuals or not path.is_file():return None
   stat=path.stat();key=(t,stat.st_size,stat.st_mtime_ns)
   if key not in self.image_hashes:self.image_hashes[key]=hashlib.sha256(path.read_bytes()).hexdigest()
   result.append((t,self.image_hashes[key]))
  return result or None
 def _window(self,index):
  page=self.pages[index]
  start=0 if index==0 else (self.pages[index-1]['lastFrameTimeMs']+page['firstFrameTimeMs'])//2
  next_time=self.pages[index+1]['firstFrameTimeMs'] if index+1<len(self.pages) else page.get('_closedAtMs')
  end=(page['lastFrameTimeMs']+next_time)//2 if next_time is not None else max([page['lastFrameTimeMs']]+[s['endMs'] for s in self.segments])
  return start,end
 def update(self,pages,segments,visuals,*,speech_complete=False,grouping_complete=False):
  with self.lock:
   self._check()
   if self.closed:raise RuntimeError('Group scheduler is closed')
   self.pages=deepcopy(sorted(pages,key=lambda p:p['pageIndex']));self.segments=deepcopy(sorted(segments,key=lambda s:s['startMs']))
   self.visuals={v['frameTimeMs']:deepcopy(v) for v in visuals}
   if len({p['pageIndex'] for p in self.pages})!=len(self.pages):raise ValueError('Duplicate group index')
   watermark=max((s['endMs'] for s in self.segments),default=-1)
   prepared=[];images=[];windows=[]
   for i,page in enumerate(self.pages):
    image=self._images(page);start,end=self._window(i)
    closed=grouping_complete or page.get('_closedAtMs') is not None or i+1<len(self.pages)
    page['_ready']=bool(image and closed and (speech_complete or watermark>=end))
    prepared.append(page);images.append(image);windows.append((start,end))
   self.pages=prepared;desired={}
   for i,page in enumerate(prepared):
    if not page['_ready']:continue
    start,end=windows[i]
    speech=[s for s in self.segments if s['startMs']<end and s['endMs']>start]
    content=self._hash(dict(page={k:v for k,v in page.items() if k not in ('_ready','_closedAtMs','imageAnalysis','textAnalysis','groupUnderstanding')},speech=speech,images=images[i]))
    neighbors=[]
    for j in (i-1,i+1):
     if 0<=j<len(prepared) and prepared[j]['_ready']:
      a,b=windows[j];neighbor_speech=[s for s in self.segments if s['startMs']<b and s['endMs']>a]
      neighbors.append(dict(page={k:v for k,v in prepared[j].items() if k not in ('_ready','_closedAtMs','imageAnalysis','textAnalysis','groupUnderstanding')},images=images[j],speech=neighbor_speech))
     else:neighbors.append(None)
    context=self._hash(dict(content=content,neighbors=neighbors))
    desired[page['pageIndex']]=dict(content=content,context=context,page=deepcopy(page),pages=deepcopy(prepared),segments=deepcopy(self.segments),visuals=deepcopy(self.visuals))
   self.desired=desired
   if not self.started and (len(desired)>=self.initial_groups or grouping_complete):self.started=True
   self._pump();self._publish();self.changed.notify_all()
 def _matches(self,index,target):
  result=self.results.get(index);meta=(result or {}).get('groupUnderstanding',{})
  return result is not None and meta.get('revision')==target['content'] and meta.get('contextRevision')==target['context']
 def _pump(self):
  if not self.started or self.closed or self.signal.is_set():return
  for index,target in list(self.desired.items()):
   if index in self.inflight or self._matches(index,target):continue
   prior=self.results.get(index);meta=(prior or {}).get('groupUnderstanding',{})
   same_content=meta.get('revision')==target['content']
   phase='link' if same_content and meta.get('status')!='failed' else 'content'
   if not same_content:self.links[index]=0
   if phase=='link' and self.links.get(index,0)>=2:
    result=deepcopy(prior);understanding=result['groupUnderstanding'];understanding['contextRevision']=target['context'];understanding['status']='partial'
    understanding.setdefault('uncertainties',[]).append('衔接复查次数已达上限，请结合整课原图检查')
    understanding['connections']={d:dict(relation='uncertain',sourceIds=[],imageIds=[],reason='衔接输入发生变化，需整课核对') for d in ('previous','next')}
    understanding['forwardImageTimesMs']=list(dict.fromkeys(understanding.get('forwardImageTimesMs',[])+target['page']['representativeFrameTimesMs']))
    self.results[index]=result;continue
   if phase=='link':self.links[index]=self.links.get(index,0)+1
   job=dict(target,phase=phase,prior=deepcopy(prior) if same_content else None)
   future=self.pool.submit(self._run,job)
   self.inflight[index]=(future,target['content'],target['context'])
   future.add_done_callback(lambda f,i=index,c=target['content'],x=target['context']:self._complete(i,c,x,f))
 def _run(self,job):
  self._check();prior=job['prior']
  with self.lock:
   spent=max(self.supplement_spent.get((job['page']['pageIndex'],job['content']),0),(prior or {}).get('groupUnderstanding',{}).get('supplementCount',0))
  remaining=max(0,self.max_supplements-spent)
  def generate():
   self._check()
   result=self.analyze(job['page'],job['pages'],job['visuals'],self.directory,job['segments'],'both',phase=job['phase'],prior=prior,max_supplements=remaining,signal=self.signal)
   self._check()
   if not isinstance(result,dict) or not isinstance(result.get('groupUnderstanding'),dict):raise ValueError('Missing group understanding')
   result=deepcopy(result)
   if result.get('pageIndex') != job['page']['pageIndex']:raise ValueError('Group identity mismatch')
   if '_visualRegions' in job['page']:result['_visualRegions']=deepcopy(job['page']['_visualRegions'])
   meta=result['groupUnderstanding'];extra=meta.get('supplementCount',0)
   if type(extra) is not int or not 0<=extra<=remaining:raise ValueError('Supplement budget exceeded')
   meta.update(revision=job['content'],contextRevision=job['context'],supplementCount=spent+extra)
   return result
  from group_understanding import GROUP_PROMPT_VERSION
  inputs=dict(promptVersion=GROUP_PROMPT_VERSION,contentRevision=job['content'],contextRevision=job['context'],phase=job['phase'],remainingSupplements=remaining,prior=prior)
  result=self.checkpoint.run('group:'+str(job['page']['pageIndex']),inputs,generate,accept=lambda r:r['groupUnderstanding'].get('status') in ('completed','partial')) if self.checkpoint else generate()
  self._check();return result
 def _failure(self,target,error):
  page=deepcopy(target['page']);page['imageAnalysis']=dict(status='failed',title='',content='',uncertainties=['本组分析未完成，原图交整课导图核对'])
  page['groupUnderstanding']=dict(status='failed',revision=target['content'],contextRevision=target['context'],knowledgeCandidates=[],exampleCandidates=[],connections={},uncertainties=['组分析失败：'+type(error).__name__],forwardImageTimesMs=page.get('representativeFrameTimesMs',[]),supplementCount=0)
  return page
 def _complete(self,index,content,context,future):
  with self.lock:
   self.inflight.pop(index,None)
   try:
    completed=future.result()
    spent=completed.get('groupUnderstanding',{}).get('supplementCount',0)
    self.supplement_spent[(index,content)]=max(self.supplement_spent.get((index,content),0),spent)
    error=None
   except BaseException as failure:completed=None;error=failure
   if not self.closed and not self.signal.is_set():
    current=self.desired.get(index)
    if current and (content,context)==(current['content'],current['context']):
     if completed is not None:self.results[index]=completed
     elif not isinstance(error,CancelledError):self.results[index]=self._failure(current,error)
    self._pump();self._publish()
   self.changed.notify_all()
 def _publish(self):
  if self.progress is None:return
  completed=sum(self._matches(i,t) for i,t in self.desired.items())
  phase='waiting_initial' if not self.started else 'completed' if completed==len(self.desired) and not self.inflight else 'linking' if any(self.results.get(i) for i in self.inflight) else 'analyzing'
  self.progress.update_groups(len(self.desired),completed,len(self.pages),phase)
 def drain(self,timeout=1800):
  deadline=time.monotonic()+timeout
  with self.changed:
   while self.inflight or (self.started and any(not self._matches(i,t) for i,t in self.desired.items())):
    self._check()
    if time.monotonic()>deadline:raise TimeoutError('Grouped analysis did not finish')
    self.changed.wait(.1)
   self._check()
 def finish(self,pages,segments,visuals):
  self.update(pages,segments,visuals,speech_complete=True,grouping_complete=True);self.drain()
  with self.lock:
   self._check()
   return [deepcopy(self.results[p['pageIndex']]) if p['pageIndex'] in self.desired else self._failure(dict(page=p,content='',context=''),ValueError('Missing image')) for p in self.pages]
 def cancel(self):
  if hasattr(self.signal,'set'):self.signal.set()
  with self.lock:
   self.closed=True
   for future,_,_ in list(self.inflight.values()):future.cancel()
   self.changed.notify_all()
  self.pool.shutdown(wait=False,cancel_futures=True)
 def close(self):
  if self.closed:return
  self.pool.shutdown(wait=True,cancel_futures=True);self.closed=True
 def __enter__(self):return self
 def __exit__(self,kind,value,trace):
  if kind:self.cancel()
  else:self.close()

import tempfile,threading,unittest
from pathlib import Path
from group_scheduler import ReadyGroupScheduler,RunSignal,cancel_run,reset_run
from concurrent.futures import CancelledError

def fixture(root,count):
 pages=[];visuals=[]
 for i in range(1,count+1):
  t=i*1000;(root/f'{t}.jpg').write_bytes(b'frame'+bytes([i]));visuals.append(dict(frameTimeMs=t,ocrBlocks=[]))
  pages.append(dict(pageIndex=i,firstFrameTimeMs=t,lastFrameTimeMs=t,memberFrameTimesMs=[t],representativeFrameTimesMs=[t],ocrLines=[],_closedAtMs=t+1000))
 speech=[dict(id='s'+str(i),startMs=i*1000,endMs=i*1000+900,text='公式条件') for i in range(count+2)]
 return pages,speech,visuals

def reply(page,*args,**kwargs):
 return dict(page,groupUnderstanding=dict(status='completed',knowledgeCandidates=[],exampleCandidates=[],connections={},uncertainties=[],supplementCount=0))
class GroupSchedulerTest(unittest.TestCase):
 def test_first_waits_for_four_then_new_ready_groups_submit_individually(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);pages,speech,visuals=fixture(root,5);calls=[]
   def analyze(page,*args,**kwargs):calls.append((page['pageIndex'],kwargs['phase']));return reply(page)
   with ReadyGroupScheduler(root,analyze) as manager:
    manager.update(pages[:3],speech,visuals);self.assertFalse(manager.started);self.assertEqual(calls,[])
    manager.update(pages[:4],speech,visuals);manager.drain();self.assertTrue(manager.started)
    manager.update(pages,speech,visuals);manager.drain()
    self.assertIn((5,'content'),calls);self.assertIn((4,'link'),calls)
 def test_short_course_starts_at_grouping_finish_and_speech_must_be_ready(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);pages,speech,visuals=fixture(root,3);calls=[]
   def analyze(page,*args,**kwargs):calls.append(page['pageIndex']);return reply(page)
   with ReadyGroupScheduler(root,analyze) as manager:
    manager.update(pages,[],visuals);self.assertEqual(calls,[])
    result=manager.finish(pages,speech,visuals);self.assertEqual(len(result),3);self.assertEqual(sorted(calls),[1,2,3])
 def test_default_five_concurrent_and_stale_group_revision_cannot_publish(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);pages,speech,visuals=fixture(root,6);gate=threading.Event();five=threading.Event();lock=threading.Lock();active=0;peak=0
   def analyze(page,*args,**kwargs):
    nonlocal active,peak
    with lock:
     active+=1;peak=max(active,peak)
     if active==5:five.set()
    gate.wait(2)
    with lock:active-=1
    return reply(page)
   with ReadyGroupScheduler(root,analyze) as manager:
    manager.update(pages,speech,visuals);self.assertTrue(five.wait(2))
    revised=[dict(p) for p in pages];revised[0]['ocrLines']=[dict(text='修订公式',sourceFrameTimeMs=1000)]
    manager.update(revised,speech,visuals);gate.set();result=manager.finish(revised,speech,visuals)
    self.assertEqual(peak,5);self.assertEqual(result[0]['ocrLines'][0]['text'],'修订公式')
 def test_cancel_then_reset_does_not_revive_old_run(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);old=RunSignal(root);cancel_run(root);reset_run(root)
   self.assertTrue(old.is_set());new=RunSignal(root);self.assertFalse(new.is_set());cancel_run(root)
   with self.assertRaises(CancelledError):new.check()
 def test_changed_input_recomputes_instead_of_reusing_group_cache(self):
  from checkpoints import Checkpoints
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);pages,speech,visuals=fixture(root,1);calls=[];cache=Checkpoints(root/'cache',{})
   def analyze(page,*args,**kwargs):calls.append(page['ocrLines']);return reply(page)
   for _ in range(2):
    with ReadyGroupScheduler(root,analyze,checkpoint=cache) as manager:manager.finish(pages,speech,visuals)
   self.assertEqual(len(calls),1)
   pages[0]['ocrLines']=[dict(text='新条件',sourceFrameTimeMs=1000)]
   with ReadyGroupScheduler(root,analyze,checkpoint=cache) as manager:manager.finish(pages,speech,visuals)
   self.assertEqual(len(calls),2)

 def test_visual_region_metadata_survives_analyzer_and_checkpoint(self):
  from checkpoints import Checkpoints
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);pages,speech,visuals=fixture(root,1);region={'mode':'ignore','nodes':[]};pages[0]['_visualRegions']=region
   def analyze(page,*args,**kwargs):return reply({k:v for k,v in page.items() if not k.startswith('_')})
   for _ in range(2):
    with ReadyGroupScheduler(root,analyze,checkpoint=Checkpoints(root/'cache',{})) as manager:
     result=manager.finish(pages,speech,visuals)
     self.assertEqual(result[0]['_visualRegions'],region)
 def test_link_rechecks_share_budget_and_cancelling_queued_futures_is_safe(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);pages,speech,visuals=fixture(root,5);calls=[]
   def analyze(page,*args,**kwargs):
    calls.append((page['pageIndex'],kwargs['phase'],kwargs['max_supplements']))
    result=reply(page);result['groupUnderstanding']['supplementCount']=min(2,kwargs['max_supplements']);return result
   with ReadyGroupScheduler(root,analyze) as manager:
    manager.update(pages[:4],speech,visuals);manager.drain()
    manager.update(pages,speech,visuals);manager.drain()
    self.assertIn((4,'link',0),calls)
    self.assertEqual(manager.results[4]['groupUnderstanding']['supplementCount'],2)
   gate=threading.Event()
   def blocked(page,*args,**kwargs):gate.wait(2);return reply(page)
   manager=ReadyGroupScheduler(root,blocked,max_workers=1)
   try:
    manager.update(pages,speech,visuals);manager.cancel()
    with self.assertRaises(CancelledError):manager.drain()
   finally:gate.set()

 def test_stale_context_completion_still_spends_same_revision_supplement_budget(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);pages,speech,visuals=fixture(root,5);entered=threading.Event();release=threading.Event();calls=[]
   def analyze(page,*args,**kwargs):
    if page['pageIndex']==4:
     calls.append(kwargs['max_supplements'])
     if len(calls)==1:entered.set();release.wait(2)
    result=reply(page);result['groupUnderstanding']['supplementCount']=min(2,kwargs['max_supplements']);return result
   with ReadyGroupScheduler(root,analyze) as manager:
    manager.update(pages[:4],speech,visuals);self.assertTrue(entered.wait(2))
    manager.update(pages,speech,visuals);release.set();manager.drain()
    self.assertEqual(calls,[2,0])
    self.assertEqual(manager.results[4]['groupUnderstanding']['supplementCount'],2)

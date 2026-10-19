"""Apply this approved bounded change with exact replacement guards."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def edit(name,old,new):
 path=ROOT/name;text=path.read_text(encoding='utf-8-sig')
 if text.count(old)!=1:raise RuntimeError(f'expected one edit target: {name}: {old[:70]}')
 path.write_text(text.replace(old,new),encoding='utf-8')
edit('agent-python/visual_evidence.py','_sample_source=None, _selected=None, _check=None) -> list[int]:','_sample_source=None, _selected=None, _check=None, _mask_selected=None) -> list[int]:')
edit('agent-python/visual_evidence.py','    originals = {}\n    def choose(ms):','    originals = {}\n    selected_masks = {}\n    def choose(ms):')
edit('agent-python/visual_evidence.py','        if _selected is not None:_selected(ms, originals[ms])','        if _mask_selected is not None:_mask_selected(ms, selected_masks.get(ms))\n        if _selected is not None:_selected(ms, originals[ms])')
edit('agent-python/visual_evidence.py','                originals={t:f for t,f in originals.items() if t in keep_times}','                originals={t:f for t,f in originals.items() if t in keep_times}\n                selected_masks={t:m for t,m in selected_masks.items() if t in keep_times}')
edit('agent-python/visual_evidence.py','                    person_frames += int(person_mask.any())','                    person_frames += int(person_mask.any())\n                    if _mask_selected is not None:selected_masks[time_ms]=person_mask.copy()')
edit('agent-python/frame_stream.py','  self.error=None;self.lock=threading.Lock();self.end=object();self.saved=0;self.queue_peak=0;self.started=time.monotonic();self.threads=[]','  self.error=None;self.lock=threading.Lock();self.end=object();self.saved=0;self.queue_peak=0;self.started=time.monotonic();self.threads=[]\n  from person_visibility import enabled\n  self.persist_masks=enabled(person_mode);self.person_masks={};self.mask_saved=0;self.mask_failed=0;self.mask_elapsed=0')
edit('agent-python/frame_stream.py',' def _select(self):\n  from visual_evidence import _candidate_times',' def _mask_selected(self,ms,mask):\n  with self.lock:self.person_masks[ms]=mask\n def _select(self):\n  from visual_evidence import _candidate_times')
edit('agent-python/frame_stream.py','_sample_source=source,_selected=lambda ms,frame:self._put(self.raw,(ms,frame)),_check=self.check)','_sample_source=source,_selected=lambda ms,frame:self._put(self.raw,(ms,frame)),_check=self.check,\n     **({"_mask_selected":self._mask_selected} if self.persist_masks else {}))')
edit('agent-python/frame_stream.py','    if self.root is not None:self.save(frame,self.root,ms,_check=lambda:self.check(force=True))\n    self.check();self.saved+=1;self._put(self.ready,item)','''    if self.root is not None:self.save(frame,self.root,ms,_check=lambda:self.check(force=True))
    if self.persist_masks:
     with self.lock:mask=self.person_masks.pop(ms,None)
     if self.root is not None:
      before=time.monotonic()
      try:
       from person_visibility import save_visibility
       save_visibility(self.root,ms,mask,(int(frame.shape[1]),int(frame.shape[0])),_check=lambda:self.check(force=True));self.mask_saved+=int(mask is not None)
      except (OSError,ValueError,TypeError) as error:
       self.mask_failed+=1
       record_event('stage_failed',self.root.name,operation='person_grouping',stage='mask_persistence',reason='person_mask_write_failed',actual_time_ms=ms,error_type=type(error).__name__)
      self.mask_elapsed+=round((time.monotonic()-before)*1000)
    self.check();self.saved+=1;self._put(self.ready,item)''')
edit('agent-python/frame_stream.py','  return False\n','''  if self.persist_masks:
   self.person_masks.clear()
   record_event('stage_completed',self.root.name if self.root else 'unbound',operation='person_grouping',stage='mask_persistence',image_count=self.saved,accepted_count=self.mask_saved,rejected_count=self.mask_failed,elapsed_ms=self.mask_elapsed)
  return False
''')
edit('agent-python/person_selection.py'," return {'personSelection':dict(config,modelRevision=revision(config['model']),runtimeRevision=revision(config['python']),libraryRevision=revision(config['libraryRoot']))}"," from person_visibility import MASK_VERSION\n return {'personSelection':dict(config,modelRevision=revision(config['model']),runtimeRevision=revision(config['python']),libraryRevision=revision(config['libraryRoot']),groupingMaskVersion=MASK_VERSION)}")
edit('agent-python/model_diagnostics.py',"_OPERATIONS={'frame_pipeline'","_OPERATIONS={'person_grouping','frame_pipeline'")
edit('agent-python/model_diagnostics.py',"_STAGES={'json_recovery'","_STAGES={'mask_persistence','page_grouping','json_recovery'")
edit('agent-python/model_diagnostics.py',"_SAFE_REASONS={'json_identical_key'","_SAFE_REASONS={'person_mask_write_failed','person_mask_unavailable','json_identical_key'")

import tempfile, unittest, threading, os
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import CancelledError
from uuid import uuid4
import cv2,numpy as np
from direct_course_map import build_direct_course_map,clean_segments
from checkpoints import Checkpoints

class DirectCourseTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.base=Path(self.tmp.name);self.id=str(uuid4());self.root=self.base/'frames'/self.id;self.root.mkdir(parents=True)
  self.pages=[];self.visuals=[]
  for i in range(1,10):
   ms=i*1000;cv2.imwrite(str(self.root/f'{ms}.jpg'),np.full((40,60,3),120,np.uint8))
   self.pages.append(dict(pageIndex=i,firstFrameTimeMs=ms,lastFrameTimeMs=ms,memberFrameTimesMs=[ms],representativeFrameTimesMs=[ms]))
   self.visuals.append(dict(frameTimeMs=ms,ocrBlocks=[]))
  self.speech=[dict(id='filler',startMs=0,endMs=500,text='嗯'),dict(id='condition',startMs=600,endMs=1000,text='  不是任意情况，只有满足条件才能应用。  ')]
 def answer(self):
  return dict(topic='课程',children=[dict(title='核心方法',sourceIds=['condition'],imageIds=['frame_1000'],children=[],details=[])],examples=[dict(title='例题',sourceIds=['condition'],imageIds=[],children=[])],uncertainties=[])
 def build(self,provider,**kw):return build_direct_course_map(self.speech,self.pages,self.visuals,self.root,ask_json=provider,**kw)
 def test_one_request_contains_every_representative_and_effective_original_speech(self):
  calls=[];result=self.build(lambda p,imgs:calls.append((p,imgs)) or self.answer())
  self.assertEqual(len(calls),1);self.assertEqual(len(calls[0][1]),9)
  self.assertEqual([s['id'] for s in calls[0][0]['effectiveTranscript']],['condition'])
  self.assertEqual(result['root']['children'][0]['evidenceRefs'][0]['quote'],self.speech[1]['text'])
  self.assertEqual(result['status'],'completed');self.assertEqual(len(result['examples']),1)
 def test_missing_image_fails_before_any_provider_and_never_subsets(self):
  (self.root/'9000.jpg').unlink();calls=[]
  result=self.build(lambda *a:calls.append(a) or self.answer())
  self.assertEqual(result['status'],'failed');self.assertEqual(calls,[])
 def test_provider_limit_does_not_retry_or_split_images(self):
  calls=[]
  def limited(p,imgs):calls.append(len(imgs));raise ValueError('image limit')
  result=self.build(limited);self.assertEqual(calls,[9]);self.assertEqual(result['status'],'failed')
 def test_cache_tracks_image_bytes_and_cancel_discards_late_reply(self):
  cache=Checkpoints(self.root/'cache',{});calls=[]
  def provider(*a):calls.append(1);return self.answer()
  self.build(provider,checkpoint=cache);self.build(provider,checkpoint=cache);self.assertEqual(len(calls),1)
  cv2.imwrite(str(self.root/'9000.jpg'),np.full((40,60,3),200,np.uint8));self.build(provider,checkpoint=cache);self.assertEqual(len(calls),2)
  signal=threading.Event()
  def late(*a):signal.set();return self.answer()
  with self.assertRaises(CancelledError):self.build(late,signal=signal)
 def test_pipeline_reviews_coverage_before_direct_map_without_page_models(self):
  import analysis
  media=self.base/'media';media.mkdir();(media/self.id).write_bytes(b'local fixture')
  calls=[]
  original_visuals=list(self.visuals)
  ms=10000;cv2.imwrite(str(self.root/f'{ms}.jpg'),np.full((40,60,3),120,np.uint8))
  self.visuals.append(dict(frameTimeMs=ms,ocrBlocks=[]))
  self.pages.append(dict(pageIndex=10,firstFrameTimeMs=ms,lastFrameTimeMs=ms,memberFrameTimesMs=[ms],representativeFrameTimesMs=[ms]))
  with patch.dict(os.environ,{'MEDIA_TEMP_DIR':str(media),'KEYFRAME_DIR':str(self.base/'frames')}), patch('analysis.transcribe_file',return_value=dict(language='zh',segments=self.speech)), patch('analysis.VisualOcrWorker') as worker, patch('analysis.group_pages',return_value=(self.pages,[])), patch('analysis.media_duration_ms',return_value=10000), patch('analysis.review_visual_coverage',return_value=(self.visuals,{'status':'completed'})) as coverage, patch('analysis.analyze_page') as page, patch('group_understanding.analyze_group') as group, patch('analysis.safe_overview') as overview, patch('course_mind_map._deepseek_course_json',side_effect=lambda p,imgs:calls.append(len(imgs)) or self.answer()):
   worker.return_value.__enter__.return_value.analyze.return_value=original_visuals
   result=analysis.analyze_file(self.id,mind_map_mode='direct',grouped_analysis=True)
  self.assertEqual(calls,[10]);self.assertEqual(result['mindMapMode'],'direct')
  self.assertEqual(len(coverage.call_args.kwargs['visuals']),9)
  self.assertEqual(len(result['visualEvidence']),10)
  coverage.assert_called_once()
  self.assertIn('coverageReview',result['stageTimingsMs'])
  for mock in (page,group,overview):mock.assert_not_called()
 def test_api_explicit_legacy_overrides_grouped_and_direct_requires_course_id(self):
  import app
  from fastapi import HTTPException
  with patch('app.build_mind_map',return_value={}) as legacy:
   app.generate_mind_map(app.MindMapRequest(segments=[],groupedAnalysis=True,mindMapMode='legacy'));legacy.assert_called_once()
  with self.assertRaises(HTTPException):app.generate_mind_map(app.MindMapRequest(segments=[],mindMapMode='direct'))

 def test_nested_classifications_survive_as_children(self):
  reply=self.answer();reply['children']=[dict(title='增长量计算',sourceIds=[],imageIds=[],children=[dict(title=title,sourceIds=[],imageIds=['frame_1000'],children=[],details=[dict(title='公式与条件',imageIds=['frame_1000'])]) for title in ['给基期、增长率','给现期、基期','给现期、增长率']])]
  result=self.build(lambda *args:reply)
  self.assertEqual(result['status'],'completed')
  self.assertEqual(len(result['root']['children'][0]['children']),3)

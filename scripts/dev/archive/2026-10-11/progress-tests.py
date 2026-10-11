from pathlib import Path
r=Path('E:/workp/videostudy')
(r/'agent-python/test_analysis_progress.py').write_text('''import json
import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from analysis_progress import AnalysisProgress

class ProgressTest(unittest.TestCase):
    def test_parallel_page_completion_is_atomic_and_unique(self):
        with tempfile.TemporaryDirectory() as d:
            progress=AnalysisProgress(Path(d))
            progress.enter('pages',3,20)
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(lambda i: progress.unit_done(str(i%20),'pages'),range(40)))
            value=json.loads((Path(d)/'progress.json').read_text())
            self.assertEqual(value,{'stage':'pages','completedStages':3,'totalStages':5,'completedUnits':20,'totalUnits':20})
            progress.enter('materials',4,2)
            progress.unit_done('old-page','pages')
            self.assertEqual(json.loads((Path(d)/'progress.json').read_text())['completedUnits'],0)

    def test_progress_failure_does_not_fail_analysis(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            with patch.object(Path,'mkdir',side_effect=OSError('disk unavailable')):
                AnalysisProgress(Path(d)).enter('media',0,2)

    def test_reported_stages_follow_actual_pipeline_and_cached_retry(self):
        import os
        from uuid import uuid4
        from unittest.mock import patch
        import analysis
        with tempfile.TemporaryDirectory() as d:
            fid=str(uuid4());(Path(d)/fid).write_bytes(b'media')
            root=Path(d)/'frames'/fid/'.analysis'
            def stage():return json.loads((root/'progress.json').read_text())
            def page(*args):
                self.assertEqual(stage()['stage'],'pages')
                return {'pageIndex':1,'imageAnalysis':{'status':'completed'}}
            def overview(*args):
                self.assertEqual(stage()['stage'],'materials')
                return {'status':'completed'}
            with patch.dict(os.environ,{'MEDIA_TEMP_DIR':d,'KEYFRAME_DIR':str(Path(d)/'frames')}), patch('analysis.transcribe_file',return_value={'language':'zh','segments':[]}) as speech, patch('analysis.VisualOcrWorker') as worker, patch('analysis.media_duration_ms',return_value=1000), patch('analysis.review_visual_coverage',return_value=([],{'status':'completed'})), patch('analysis.group_pages',return_value=([{'pageIndex':1}],[])), patch('analysis.analyze_page',side_effect=page), patch('analysis.safe_overview',side_effect=overview), patch('analysis.build_mind_map',return_value={'status':'completed'}):
                worker.return_value.__enter__.return_value.analyze.return_value=[]
                analysis.analyze_file(fid)
                self.assertEqual(stage()['stage'],'saving')
                self.assertEqual(stage()['completedStages'],4)
                analysis.analyze_file(fid)
                self.assertEqual(speech.call_count,1)
                self.assertEqual(stage()['stage'],'saving')
''',encoding='utf-8')
(r/'desktop/src/analysisProgress.test.mjs').write_text('''import test from 'node:test'
import assert from 'node:assert/strict'
import {progressView} from './analysisProgress.ts'
test('real page counts advance bar and completion depends on stored job status',()=>{
 const snapshot={stage:'pages',completedStages:3,totalStages:5,completedUnits:8,totalUnits:20}
 const view=progressView('processing',snapshot)
 assert.equal(view.label,'页面解读 · 已完成 8 / 20 页');assert.equal(view.ratio,.68)
 assert.equal(progressView('completed',null).ratio,1)
 assert.equal(progressView('processing',{...snapshot,stage:'saving',completedStages:4,completedUnits:0,totalUnits:0}).ratio,.8)
})
test('queue and missing data stay indeterminate and failed tasks retain last actual progress',()=>{
 assert.equal(progressView('queued',null).indeterminate,true)
 assert.equal(progressView('processing',null).indeterminate,true)
 assert.equal(progressView('failed',{stage:'pages',completedStages:3,totalStages:5,completedUnits:8,totalUnits:20}).ratio,.68)
 assert.equal(progressView('processing',{stage:'pages',completedStages:NaN,totalStages:5,completedUnits:0,totalUnits:20}).indeterminate,true)
 assert.equal(progressView('processing',{stage:'pages',completedStages:5,totalStages:5,completedUnits:20,totalUnits:20}).indeterminate,true)
})
''',encoding='utf-8')
base=r/'backend-java/src/test/java/cn/videostudy/api'
imports=(base/'IgnoredRegionTest.java').read_text().split('class IgnoredRegionTest')[0]
(base/'AnalysisProgressTest.java').write_text(imports+'''class AnalysisProgressTest {
 @TempDir Path directory;
 @Test void readsOnlyTaskProgressAndPreservesOldFourFieldConstructor() throws Exception {
  var store=mock(TranscriptionJobStore.class);
  var controller=new TranscriptionController(directory.toString(),"full",store,mock(MediaAnalyzer.class));
  org.springframework.test.util.ReflectionTestUtils.setField(controller,"keyframeDirectory",directory.toString());
  var id=UUID.randomUUID().toString();var other=UUID.randomUUID().toString();
  var path=directory.resolve(id).resolve(".analysis");Files.createDirectories(path);
  Files.writeString(path.resolve("progress.json"),"{\\"stage\\":\\"pages\\",\\"completedStages\\":3,\\"totalStages\\":5,\\"completedUnits\\":8,\\"totalUnits\\":20}");
  when(store.find(id)).thenReturn(Optional.of(new TranscriptionController.TranscriptionJob(id,"processing",null,null)));
  when(store.find(other)).thenReturn(Optional.of(new TranscriptionController.TranscriptionJob(other,"processing",null,null)));
  try {
   var mvc=MockMvcBuilders.standaloneSetup(controller).build();
   mvc.perform(get("/api/transcriptions/"+id)).andExpect(status().isOk()).andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath("$.progress.completedUnits").value(8));
   mvc.perform(get("/api/transcriptions/"+other)).andExpect(status().isOk()).andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath("$.progress").doesNotExist());
   Files.writeString(path.resolve("progress.json"),"broken");
   mvc.perform(get("/api/transcriptions/"+id)).andExpect(status().isOk()).andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath("$.progress").doesNotExist());
   when(store.find(id)).thenReturn(Optional.of(new TranscriptionController.TranscriptionJob(id,"completed",null,null)));
   mvc.perform(get("/api/transcriptions/"+id)).andExpect(status().isOk()).andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath("$.progress").doesNotExist());
  } finally {controller.close();}
 }
}
''',encoding='utf-8')

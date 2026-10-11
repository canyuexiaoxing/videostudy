from pathlib import Path
root=Path(r'E:\workp\videostudy')
(root/'agent-python/test_sampling_interval.py').write_text('''import io
import os
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import Mock, patch
import numpy as np
from visual_evidence import _candidate_times
from analysis import analyze_file
from app import TranscribeRequest
from pydantic import ValidationError

class SamplingIntervalTests(unittest.TestCase):
    def test_sampling_filter_and_timestamps_follow_selected_interval(self):
        for seconds in (2,3,4):
            with self.subTest(seconds=seconds):
                process=Mock()
                process.stdout=io.BytesIO(b''.join(np.full((180,320),v,np.uint8).tobytes() for v in (0,100,200)))
                process.stderr=io.BytesIO()
                process.wait.return_value=0
                process.poll.return_value=0
                with patch('visual_evidence.subprocess.Popen',return_value=process) as launch:
                    times=_candidate_times(Path('fixture'),sample_seconds=seconds)
                self.assertEqual(times,[0,seconds*1000,seconds*2000])
                self.assertIn(f'fps=1/{seconds}',launch.call_args.args[0][launch.call_args.args[0].index('-vf')+1])

    def test_invalid_interval_is_rejected_before_media_processing(self):
        for value in (0,1,5,2.5):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                TranscribeRequest(fileId='fixture',coarseSampleSeconds=value)
        self.assertEqual(TranscribeRequest(fileId='fixture').coarseSampleSeconds,2)

    def test_interval_reaches_worker_and_invalidates_analysis_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            file_id=str(uuid4())
            (Path(directory)/file_id).write_bytes(b'fixture')
            with patch.dict(os.environ,{'MEDIA_TEMP_DIR':directory,'KEYFRAME_DIR':str(Path(directory)/'frames')}), \\
                 patch('analysis.transcribe_file',return_value={'language':'zh','segments':[]}), \\
                 patch('analysis.VisualOcrWorker') as worker, \\
                 patch('analysis.media_duration_ms',return_value=10000), \\
                 patch('analysis.review_visual_coverage',return_value=([],{'status':'not_applicable'})), \\
                 patch('analysis.group_pages',return_value=([],[])):
                worker.return_value.__enter__.return_value.analyze.return_value=[]
                analyze_file(file_id,coarse_sample_seconds=2)
                result=analyze_file(file_id,coarse_sample_seconds=4)
                self.assertEqual(worker.call_args.kwargs['sample_seconds'],4)
                self.assertEqual(worker.return_value.__enter__.return_value.analyze.call_count,2)
                self.assertEqual(result['coarseSampleSeconds'],4)
''',encoding='utf-8')
(root/'backend-java/src/test/java/cn/videostudy/api/SamplingIntervalTest.java').write_text('''package cn.videostudy.api;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.datasource.embedded.*;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;
import org.springframework.jdbc.core.JdbcTemplate;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.client.RestClient;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.http.MediaType;
import java.nio.file.*;
import java.util.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

class SamplingIntervalTest {
 @TempDir Path directory;
 @Test void selectionSurvivesUploadAndRetry() throws Exception {
  var store=mock(TranscriptionJobStore.class);
  var analyzer=mock(MediaAnalyzer.class);
  var controller=new TranscriptionController(directory.toString(),"full",store,analyzer);
  try {
   var mvc=MockMvcBuilders.standaloneSetup(controller).build();
   mvc.perform(multipart("/api/transcriptions").file(new MockMultipartFile("file","lesson.mp4","video/mp4",new byte[]{1})).param("coarseSampleSeconds","4"))
    .andExpect(status().isAccepted());
   verify(store).createQueued(anyString(),eq("both"),eq(2.0),eq(4));
   verify(analyzer,timeout(3000)).analyze(anyString(),eq("full"),eq("both"),eq(2.0),eq(4),isNull());
   var id=UUID.randomUUID().toString();Files.write(directory.resolve(id),new byte[]{1});
   when(store.find(id)).thenReturn(Optional.of(new TranscriptionController.TranscriptionJob(id,"failed",null,"failed")));
   when(store.markQueuedIfFailed(id)).thenReturn(true);
   when(store.findVisualAnalysisMode(id)).thenReturn("both");
   when(store.findCoarseChangePercent(id)).thenReturn(2.0);
   when(store.findCoarseSampleSeconds(id)).thenReturn(3);
   mvc.perform(post("/api/transcriptions/"+id+"/retry")).andExpect(status().isAccepted());
   verify(analyzer,timeout(3000)).analyze(eq(id),eq("full"),eq("both"),eq(2.0),eq(3),isNull());
   mvc.perform(multipart("/api/transcriptions").file(new MockMultipartFile("file","lesson.mp4","video/mp4",new byte[]{1})).param("coarseSampleSeconds","5"))
    .andExpect(status().isBadRequest()).andExpect(jsonPath("$.error").value("invalid_coarse_sample_seconds"));
  } finally { controller.close(); }
 }
 @Test void storesSelectedIntervalAndDefaultsOlderJobsToTwo() {
  var ds=new EmbeddedDatabaseBuilder().setType(EmbeddedDatabaseType.H2).generateUniqueName(true).build();
  try {
   new ResourceDatabasePopulator(new ClassPathResource("db/migration/V1__create_transcription_jobs.sql"),new ClassPathResource("db/migration/V3__visual_analysis_mode.sql"),new ClassPathResource("db/migration/V4__coarse_change_percent.sql"),new ClassPathResource("db/migration/V10__coarse_sample_seconds.sql")).execute(ds);
   var store=new TranscriptionJobStore(new JdbcTemplate(ds),new ObjectMapper());
   store.createQueued("old");store.createQueued("new","both",2.0,4);
   assertEquals(2,store.findCoarseSampleSeconds("old"));assertEquals(4,store.findCoarseSampleSeconds("new"));
  } finally { ds.shutdown(); }
 }
 @Test void httpTransportCarriesIntervalAlongsideSubtitleCallback() {
  var builder=RestClient.builder().baseUrl("http://agent");var server=MockRestServiceServer.bindTo(builder).build();
  server.expect(requestTo("http://agent/analyze")).andExpect(jsonPath("$.coarseSampleSeconds").value(4))
   .andExpect(jsonPath("$.subtitleCallbackToken").value("token"))
   .andRespond(withSuccess("{\\"language\\":\\"zh\\",\\"segments\\":[]}",MediaType.APPLICATION_JSON));
  new HttpMediaAnalyzer(builder.build()).analyze("id","full","both",2.0,4,"token");server.verify();
 }
}
''',encoding='utf-8')

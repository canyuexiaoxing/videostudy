package cn.videostudy.api;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.mock.web.*;
import java.nio.file.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
class NativeRuntimeControllerTest {
 @TempDir Path folder;
 JdbcTemplate jdbc;NativeRuntimeController controller;PreviewActivity foreground;
 @BeforeEach void setup(){jdbc=new JdbcTemplate(SQLiteStoreTest.database(folder.resolve("activity.db")));foreground=new PreviewActivity();controller=new NativeRuntimeController(jdbc,foreground,new ObjectMapper(),folder.toString(),"test-native",()->{});}
 @Test void readinessProtocolAndIdleAreExplicit(){assertEquals(Map.of("status","ready","storage","sqlite","role","local","protocolVersion",1),controller.health().getBody());assertEquals(Map.of("activeJobs",0,"busy",false),controller.activity().getBody());}
 @Test void databaseJobsAndBothChatLocksPreventMaintenance(){
  var json=new ObjectMapper();String course=UUID.randomUUID().toString();new TranscriptionJobStore(jdbc,json).createQueued(course);
  assertEquals(true,controller.activity().getBody().get("busy"));jdbc.update("UPDATE transcription_jobs SET status='completed' WHERE id=?",course);
  var chats=new OverviewChatStore(jdbc,json);String thread=chats.thread(course,"context","client");assertTrue(chats.claim(thread,"run"));assertEquals(1,controller.activity().getBody().get("activeJobs"));chats.release(thread,"run");
  var practice=new PracticeStore(jdbc,json);var set=practice.request(course,"hash","request","title",Map.of(),false);assertEquals(1,controller.activity().getBody().get("activeJobs"));
  var run=practice.claim(set.id()).orElseThrow();practice.complete(run,Map.of("questions",List.of()));
  var question=new QuestionChatStore(jdbc,json);String qthread=question.thread(set.id(),"question","client");assertTrue(question.claim(qthread,"question-run"));assertEquals(1,controller.activity().getBody().get("activeJobs"));question.release(qthread,"question-run");assertEquals(false,controller.activity().getBody().get("busy"));
 }
 @Test void foregroundAndCompatibilityWorkPreventMaintenance()throws Exception{
  var req=new MockHttpServletRequest("POST","/api/work");foreground.preHandle(req,new MockHttpServletResponse(),null);assertEquals(true,controller.activity().getBody().get("busy"));foreground.afterCompletion(req,new MockHttpServletResponse(),null,null);
  Path job=folder.resolve("compatibility").resolve(UUID.randomUUID().toString());Files.createDirectories(job);assertEquals(true,controller.activity().getBody().get("busy"));Files.writeString(job.resolve("status.json"),"{\"status\":\"completed\"}");assertEquals(false,controller.activity().getBody().get("busy"));Files.writeString(job.resolve("status.json"),"invalid");assertEquals(503,controller.activity().getStatusCode().value());assertEquals(true,controller.activity().getBody().get("busy"));
 }
 @Test void failedActivityCheckFailsClosed(){jdbc.execute("DROP TABLE overview_jobs");assertEquals(503,controller.activity().getStatusCode().value());assertEquals(true,controller.activity().getBody().get("busy"));}
 @Test void legacyUnprotectedModeHasNoRuntimeManagementEndpoints(){var legacy=new NativeRuntimeController(jdbc,foreground,new ObjectMapper(),folder.toString());assertEquals(404,legacy.health().getStatusCode().value());assertEquals(404,legacy.activity().getStatusCode().value());assertEquals(404,legacy.shutdown().getStatusCode().value());}
 @Test void nativeShutdownReturnsBeforeInvokingInjectedGracefulCloseAndIsIdempotent()throws Exception{var latch=new java.util.concurrent.CountDownLatch(1);var calls=new java.util.concurrent.atomic.AtomicInteger();var nativeController=new NativeRuntimeController(jdbc,foreground,new ObjectMapper(),folder.toString(),"test-native",()->{calls.incrementAndGet();latch.countDown();});assertEquals(202,nativeController.shutdown().getStatusCode().value());assertEquals(202,nativeController.shutdown().getStatusCode().value());assertTrue(latch.await(5,java.util.concurrent.TimeUnit.SECONDS));assertEquals(1,calls.get());}
}

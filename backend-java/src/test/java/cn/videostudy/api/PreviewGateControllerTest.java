package cn.videostudy.api;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import java.nio.file.*;import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
class PreviewGateControllerTest {
 @TempDir Path directory;
 JdbcTemplate jdbc;TranscriptionJobStore main;PreviewGateController gate;
 String id=UUID.randomUUID().toString(); PreviewActivity activity;
 @BeforeEach void setup(){
  jdbc=new JdbcTemplate(new DriverManagerDataSource("jdbc:h2:mem:"+UUID.randomUUID()+";MODE=MySQL;DB_CLOSE_DELAY=-1","sa",""));
  for(var table:List.of("transcription_jobs","overview_jobs","chapter_jobs","subtitle_jobs","practice_sets")) jdbc.execute("CREATE TABLE "+table+" (status VARCHAR(24),transcription_id VARCHAR(36))");
  jdbc.execute("CREATE TABLE question_chat_threads (lock_until BIGINT)");
  main=mock(TranscriptionJobStore.class);ready("completed","completed");
  jdbc.update("INSERT INTO overview_jobs VALUES ('completed',?)",id);
  activity=new PreviewActivity();gate=new PreviewGateController(jdbc,main,new ObjectMapper(),directory.toString(),activity);
 }
 void ready(String status,String map){var mind=new TranscriptionController.MindMapResult(map,null,null,null);
  var result=new TranscriptionController.TranscriptResult("zh",List.of(),List.of(),null,null,null,List.of(),List.of(),"both","v1",3.0,mind);
  when(main.find(id)).thenReturn(Optional.of(new TranscriptionController.TranscriptionJob(id,status,result,null)));
 }
 @Test void requiresBothCompletedMapAndCompletedOverview(){
  assertTrue(gate.check(id).allowed());ready("completed","failed");assertFalse(gate.check(id).allowed());ready("completed","completed");
  jdbc.update("UPDATE overview_jobs SET status='processing'");assertFalse(gate.check(id).allowed());jdbc.update("UPDATE overview_jobs SET status='failed'");assertFalse(gate.check(id).allowed());
 }
 @Test void everyForegroundQueueBlocksAndReleasingItAllowsGeneration(){
  for(var table:List.of("transcription_jobs","overview_jobs","chapter_jobs","subtitle_jobs","practice_sets")){
   jdbc.update("INSERT INTO "+table+" VALUES ('queued',NULL)");assertFalse(gate.check(id).allowed(),table);jdbc.update("DELETE FROM "+table+" WHERE transcription_id IS NULL");assertTrue(gate.check(id).allowed());
  }
  jdbc.update("INSERT INTO question_chat_threads VALUES (?)",System.currentTimeMillis()+60000);assertFalse(gate.check(id).allowed());
 }
 @Test void activeCompatibilityConversionAndUnreadableStateFailClosed()throws Exception{
  var folder=directory.resolve("compatibility").resolve(UUID.randomUUID().toString());Files.createDirectories(folder);var status=folder.resolve("status.json");
  Files.writeString(status,"{\"status\":\"processing\"}");assertFalse(gate.check(id).allowed());Files.writeString(status,"{\"status\":\"completed\"}");assertTrue(gate.check(id).allowed());Files.writeString(status,"{");assertFalse(gate.check(id).allowed());
 }
 @Test void synchronousRegenerationBlocksWithoutChangingAnyJobRow(){
  var request=new org.springframework.mock.web.MockHttpServletRequest("POST","/api/transcriptions/"+id+"/mind-map");
  activity.preHandle(request,null,null);assertFalse(gate.check(id).allowed());
  activity.afterCompletion(request,null,null,new RuntimeException("test"));assertTrue(gate.check(id).allowed());
  activity.afterCompletion(request,null,null,null);assertFalse(activity.busy());
 }
 @Test void invalidOrMissingCourseIsNeverAllowed(){assertFalse(gate.check("../bad").allowed());when(main.find(id)).thenReturn(Optional.empty());assertFalse(gate.check(id).allowed());}
}

package cn.videostudy.api;
import org.junit.jupiter.api.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;
import org.springframework.core.io.ClassPathResource;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
class OverviewChatTest {
 JdbcTemplate jdbc;OverviewChatController controller;OverviewChatStore store;TranscriptionJobStore main;MediaAnalyzer agent;
 String course=UUID.randomUUID().toString(),client=UUID.randomUUID().toString();ObjectMapper json=new ObjectMapper();
 @BeforeEach void setup()throws Exception{
  var ds=new DriverManagerDataSource("jdbc:h2:mem:"+UUID.randomUUID()+";MODE=MySQL;DB_CLOSE_DELAY=-1","sa","");new ResourceDatabasePopulator(new ClassPathResource("db/migration/V1__create_transcription_jobs.sql"),new ClassPathResource("db/migration/V7__overview_jobs.sql"),new ClassPathResource("db/migration/V17__overview_chat.sql")).execute(ds);jdbc=new JdbcTemplate(ds);
  jdbc.update("INSERT INTO transcription_jobs(id,status) VALUES (?,'completed')",course);
  jdbc.update("INSERT INTO overview_jobs(transcription_id,status,result_json) VALUES (?,'completed',?)",course,json.writeValueAsString(Map.of("status","completed","headline","hidden initial overview")));
  var result=json.readValue("{\"language\":\"zh\",\"segments\":[{\"id\":\"s1\",\"startMs\":1000,\"endMs\":2000,\"text\":\"teacher method\"}]}",TranscriptionController.TranscriptResult.class);
  main=mock(TranscriptionJobStore.class);when(main.find(course)).thenReturn(Optional.of(new TranscriptionController.TranscriptionJob(course,"completed",result,null)));
  agent=mock(MediaAnalyzer.class);when(agent.chatOverview(anyMap())).thenReturn(Map.of("reply","explained answer","citations",List.of(Map.of("sourceId","s1","startMs",1000,"endMs",2000,"quote","teacher method")),"contextMode","restored"));store=new OverviewChatStore(jdbc,json);controller=new OverviewChatController(jdbc,json,main,store,agent);
 }
 String context(){return (String)controller.history(course,client).get("contextKey");}
 @Test void hidesInitialMessagesPersistsFollowupsAndDoesNotRepeatPaidRequest(){
  var before=controller.history(course,client);assertEquals(List.of(),before.get("messages"));assertFalse(before.containsKey("overview"));String key=context(),request=UUID.randomUUID().toString();var body=new OverviewChatController.Request(key,request,"why?");
  assertEquals(200,controller.send(course,client,body).getStatusCode().value());assertEquals(200,controller.send(course,client,body).getStatusCode().value());verify(agent,times(1)).chatOverview(anyMap());assertEquals(2,((List<?>)controller.history(course,client).get("messages")).size());
  assertEquals(0,((List<?>)controller.history(course,UUID.randomUUID().toString()).get("messages")).size());
  assertEquals(409,controller.send(course,client,new OverviewChatController.Request(key,request,"different question")).getStatusCode().value());
  jdbc.update("DELETE FROM transcription_jobs WHERE id=?",course);assertEquals(0,jdbc.queryForObject("SELECT COUNT(*) FROM overview_chat_turns",Integer.class));
 }
 @Test void providerFailureIsRetryableAndChangedOverviewCannotMixThreads()throws Exception{
  String key=context();var body=new OverviewChatController.Request(key,UUID.randomUUID().toString(),"why?");when(agent.chatOverview(anyMap())).thenThrow(new IllegalStateException());assertEquals(502,controller.send(course,client,body).getStatusCode().value());assertEquals(0,((List<?>)controller.history(course,client).get("messages")).size());
  doReturn(Map.of("reply","recovered","citations",List.of())).when(agent).chatOverview(anyMap());assertEquals(200,controller.send(course,client,body).getStatusCode().value());
  jdbc.update("UPDATE overview_jobs SET result_json=? WHERE transcription_id=?",json.writeValueAsString(Map.of("status","completed","headline","new overview")),course);assertEquals(409,controller.send(course,client,new OverviewChatController.Request(key,UUID.randomUUID().toString(),"next")).getStatusCode().value());assertEquals(List.of(),controller.history(course,client).get("messages"));
 }
 @Test void usesAllFollowupHistoryAndRejectsInventedCitation(){
  String key=context();controller.send(course,client,new OverviewChatController.Request(key,UUID.randomUUID().toString(),"first"));
  when(agent.chatOverview(anyMap())).thenAnswer(call->{Map<?,?> payload=call.getArgument(0);assertEquals(2,((List<?>)payload.get("history")).size());assertTrue(payload.containsKey("overview"));assertTrue(payload.containsKey("source"));return Map.of("reply","bad","citations",List.of(Map.of("sourceId","invented")));});
  assertEquals(502,controller.send(course,client,new OverviewChatController.Request(key,UUID.randomUUID().toString(),"second")).getStatusCode().value());assertEquals(2,((List<?>)controller.history(course,client).get("messages")).size());
 }
}

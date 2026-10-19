package cn.videostudy.api;
import org.junit.jupiter.api.Test;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.core.type.TypeReference;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
class PracticeDiagramValidationTest {
 ObjectMapper json=new ObjectMapper();
 List<Map<String,Object>> fixtures()throws Exception{try(var stream=getClass().getResourceAsStream("/practice-math-fixtures.json")){return json.readValue(stream,new TypeReference<List<Map<String,Object>>>(){});}}
 Map<String,Object> source(List<Map<String,Object>> questions){return Map.of("count",questions.size(),"nodes",List.of(Map.of("id","n1","evidenceRefs",questions.getFirst().get("citations"))));}
 @Test void acceptsRealPythonValidatedMathAndEverySupportedDiagram()throws Exception{
  var questions=fixtures();assertDoesNotThrow(()->PracticeController.validate(Map.of("status","completed","questions",questions),source(questions)));
  var first=questions.getFirst();first.put("diagram",Map.of("kind","svg"));assertThrows(IllegalArgumentException.class,()->PracticeController.validate(Map.of("status","completed","questions",questions),source(questions)));
 }
 @Test void databaseAndPublicApiKeepFormulasAndStructuredFiguresWithoutAnswers()throws Exception{
  var ds=new org.springframework.jdbc.datasource.DriverManagerDataSource("jdbc:h2:mem:"+UUID.randomUUID()+";MODE=MySQL;DB_CLOSE_DELAY=-1","sa","");new org.springframework.jdbc.datasource.init.ResourceDatabasePopulator(new org.springframework.core.io.ClassPathResource("db/migration/V1__create_transcription_jobs.sql"),new org.springframework.core.io.ClassPathResource("db/migration/V8__practice.sql")).execute(ds);
  var jdbc=new org.springframework.jdbc.core.JdbcTemplate(ds);String course=UUID.randomUUID().toString();jdbc.update("INSERT INTO transcription_jobs(id,status) VALUES (?,'completed')",course);var store=new PracticeStore(jdbc,json);var questions=fixtures();var source=source(questions);var job=store.request(course,"hash","key","math",source,false);store.complete(store.claim(job.id()).orElseThrow(),Map.of("status","completed","questions",questions));
  var exposed=(List<?>)store.publicSet(course,job.id()).get("questions");assertEquals(questions.size(),exposed.size());
  for(int i=0;i<questions.size();i++){var q=(Map<?,?>)exposed.get(i);assertEquals(questions.get(i).get("prompt"),q.get("prompt"));assertEquals(questions.get(i).get("diagram"),q.get("diagram"));assertFalse(q.containsKey("answerIndex"));}
 }
}

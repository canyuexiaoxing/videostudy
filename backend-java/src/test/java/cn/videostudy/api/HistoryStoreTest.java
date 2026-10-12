package cn.videostudy.api;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;
import org.springframework.core.io.ClassPathResource;
import java.util.UUID;
import static org.junit.jupiter.api.Assertions.*;
class HistoryStoreTest {
 @Test void historyIncludesAllStatesWithoutReadingResultAndDeletionRemovesMembership(){
  var ds=new DriverManagerDataSource("jdbc:h2:mem:"+UUID.randomUUID()+";MODE=MySQL;DB_CLOSE_DELAY=-1","sa","");
  new ResourceDatabasePopulator(new ClassPathResource("db/migration/V1__create_transcription_jobs.sql"),new ClassPathResource("db/migration/V12__history_filename.sql")).execute(ds);
  var jdbc=new JdbcTemplate(ds);var store=new TranscriptionJobStore(jdbc,new ObjectMapper());
  var old=UUID.randomUUID().toString();var fresh=UUID.randomUUID().toString();
  jdbc.update("INSERT INTO transcription_jobs(id,status,created_at,result_json) VALUES (?,'expired','2025-01-01','invalid result JSON')",old);
  jdbc.update("INSERT INTO transcription_jobs(id,status,created_at) VALUES (?,'completed','2026-01-01')",fresh);
  store.saveOriginalFilename(fresh,"C:/private/课程.mp4");
  var rows=store.listHistory();assertEquals(2,rows.size());assertEquals(fresh,rows.getFirst().id());assertEquals("课程.mp4",rows.getFirst().name());assertEquals("expired",rows.getLast().status());assertNull(rows.getLast().name());assertNotNull(rows.getFirst().createdAt());
  store.delete(fresh);assertEquals(old,store.listHistory().getFirst().id());
 }
}

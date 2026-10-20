package cn.videostudy.api;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.jdbc.core.JdbcTemplate;
import org.sqlite.SQLiteDataSource;
import org.flywaydb.core.Flyway;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.*;
import static org.junit.jupiter.api.Assertions.*;
class SQLiteStoreTest {
 @TempDir Path folder;
 static SQLiteDataSource database(Path file){var ds=new SQLiteDataSource();ds.setUrl("jdbc:sqlite:"+file+"?foreign_keys=on&busy_timeout=10000&journal_mode=WAL&date_class=TEXT&transaction_mode=IMMEDIATE");Flyway.configure().dataSource(ds).locations("classpath:db/sqlite").load().migrate();return ds;}
 @Test void schemaPersistsAndReopensWithAllSettingsAndCascade(){
  var file=folder.resolve("study.db");var jdbc=new JdbcTemplate(database(file));var store=new TranscriptionJobStore(jdbc,new ObjectMapper());String id=UUID.randomUUID().toString();store.createQueued(id);store.saveOriginalFilename(id,"lesson.mp4");store.saveMediaIdentity(id,new MediaIdentity(123,"a".repeat(64)));assertEquals(1,store.listHistory().size());assertNotNull(store.listHistory().getFirst().createdAt());
  var reopened=new JdbcTemplate(database(file));assertEquals("lesson.mp4",new TranscriptionJobStore(reopened,new ObjectMapper()).listHistory().getFirst().name());
  var subtitles=new SubtitleJobStore(jdbc,new ObjectMapper());subtitles.request(id,"en",false);assertTrue(subtitles.find(id,"en").isPresent());jdbc.update("DELETE FROM transcription_jobs WHERE id=?",id);assertEquals(0,jdbc.queryForObject("SELECT COUNT(*) FROM subtitle_jobs",Integer.class));
 }
 @Test void concurrentSubtitleRequestsDoNotDuplicateOrLoseWork()throws Exception{
  var jdbc=new JdbcTemplate(database(folder.resolve("concurrent.db")));var json=new ObjectMapper();String id=UUID.randomUUID().toString();new TranscriptionJobStore(jdbc,json).createQueued(id);var store=new SubtitleJobStore(jdbc,json);var pool=Executors.newFixedThreadPool(4);
  try{var jobs=new ArrayList<Future<?>>();for(int i=0;i<12;i++)jobs.add(pool.submit(()->store.request(id,"en",false)));for(var job:jobs)job.get(20,TimeUnit.SECONDS);assertEquals(1,jdbc.queryForObject("SELECT COUNT(*) FROM subtitle_jobs",Integer.class));}finally{pool.shutdownNow();}
 }
 @Test void practiceAndChatDuplicateRequestsKeepOneRecord(){
  var jdbc=new JdbcTemplate(database(folder.resolve("chat.db")));var json=new ObjectMapper();String id=UUID.randomUUID().toString(),client=UUID.randomUUID().toString();new TranscriptionJobStore(jdbc,json).createQueued(id);var practice=new PracticeStore(jdbc,json);var first=practice.request(id,"hash","request","test",Map.of("count",1),false);assertEquals(first.id(),practice.request(id,"hash","request","test",Map.of("count",1),false).id());var chats=new OverviewChatStore(jdbc,json);String thread=chats.thread(id,"context",client);assertEquals(thread,chats.thread(id,"context",client));assertTrue(chats.claim(thread,"token"));chats.save(thread,"token",UUID.randomUUID().toString(),"question",Map.of("reply","answer","citations",List.of()));assertEquals(2,chats.history(thread).size());
 }
 @Test void repeatedOverviewAndChapterRequestsReuseSQLiteJobs(){
  var jdbc=new JdbcTemplate(database(folder.resolve("repeated-jobs.db")));var json=new ObjectMapper();var main=new TranscriptionJobStore(jdbc,json);String id=UUID.randomUUID().toString();main.createQueued(id);
  var agent=org.mockito.Mockito.mock(MediaAnalyzer.class);
  var overview=new OverviewController(jdbc,json,main,agent){@Override public void dispatch(){}};
  var chapters=new ChapterController(jdbc,json,main,agent){@Override public void dispatch(){}};
  try{overview.request(id);chapters.request(id);assertDoesNotThrow(()->overview.request(id));assertDoesNotThrow(()->chapters.request(id));assertEquals(1,jdbc.queryForObject("SELECT COUNT(*) FROM overview_jobs",Integer.class));assertEquals(1,jdbc.queryForObject("SELECT COUNT(*) FROM chapter_jobs",Integer.class));org.mockito.Mockito.verifyNoInteractions(agent);}finally{overview.close();chapters.close();}
 }
 @Test void sqliteTimestampsAreCorrectInUsersTimezone(){
  var previous=TimeZone.getDefault();try{TimeZone.setDefault(TimeZone.getTimeZone("Asia/Shanghai"));var jdbc=new JdbcTemplate(database(folder.resolve("timezone.db")));var main=new TranscriptionJobStore(jdbc,new ObjectMapper());String id=UUID.randomUUID().toString();main.createQueued(id);var created=main.listHistory().getFirst().createdAt();assertTrue(Math.abs(java.time.Duration.between(created,java.time.Instant.now()).toSeconds())<5,"SQLite created_at must represent actual UTC time");var subtitles=new SubtitleJobStore(jdbc,new ObjectMapper());subtitles.request(id,"en",false);subtitles.captureSource(id,subtitles.callbackToken(id),new SubtitleJobStore.Source("zh",List.of(new TranscriptionController.TranscriptSegment("t1",0,1000,"test")),List.of()));var run=subtitles.claim(id,"en",3).orElseThrow();subtitles.retry(run,java.time.Instant.now().minusSeconds(2));assertEquals(1,subtitles.due(10,3).size());var retry=subtitles.claim(id,"en",3).orElseThrow();subtitles.retry(retry,java.time.Instant.now().plusSeconds(3600));assertEquals(0,subtitles.due(10,3).size());}finally{TimeZone.setDefault(previous);}
 }

}

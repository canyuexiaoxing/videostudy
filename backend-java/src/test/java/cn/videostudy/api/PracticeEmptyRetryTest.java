package cn.videostudy.api;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;
import org.springframework.core.io.ClassPathResource;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import static org.junit.jupiter.api.Assertions.*;
class PracticeEmptyRetryTest {
 @TempDir Path folder;
 record Fixture(JdbcTemplate jdbc,PracticeStore store,String course){}
 Fixture fixture(boolean sqlite){
  javax.sql.DataSource ds;if(sqlite)ds=SQLiteStoreTest.database(folder.resolve(UUID.randomUUID()+".db"));else{ds=new DriverManagerDataSource("jdbc:h2:mem:"+UUID.randomUUID()+";MODE=MySQL;DB_CLOSE_DELAY=-1","sa","");new ResourceDatabasePopulator(new ClassPathResource("db/migration/V1__create_transcription_jobs.sql"),new ClassPathResource("db/migration/V8__practice.sql")).execute(ds);}
  var jdbc=new JdbcTemplate(ds);String course=UUID.randomUUID().toString();jdbc.update("INSERT INTO transcription_jobs(id,status) VALUES (?,'completed')",course);return new Fixture(jdbc,new PracticeStore(jdbc,new ObjectMapper()),course);
 }
 @ParameterizedTest @ValueSource(booleans={false,true}) void emptyCompletedSetRequiresExplicitRetryAndResetsRun(boolean sqlite){
  var f=fixture(sqlite);var set=f.store.request(f.course,"hash","key","title",Map.of(),false);var old=f.store.claim(set.id()).orElseThrow();f.store.complete(old,Map.of("questions",List.of()));
  assertEquals("completed",f.store.request(f.course,"hash","key","title",Map.of(),false).status());
  var retry=f.store.request(f.course,"hash","key","title",Map.of(),true);assertEquals(set.id(),retry.id());assertEquals("queued",retry.status());assertNull(retry.result());assertNull(retry.error());assertEquals(0,f.jdbc.queryForObject("SELECT attempt_count FROM practice_sets WHERE id=?",Integer.class,set.id()));
  var active=f.store.claim(set.id()).orElseThrow();f.store.complete(old,Map.of("questions",List.of(Map.of("id","stale"))));assertEquals("processing",f.store.find(set.id()).orElseThrow().status());f.store.complete(active,Map.of("questions",List.of(Map.of("id","new"))));assertEquals("completed",f.store.find(set.id()).orElseThrow().status());
 }
 @ParameterizedTest @ValueSource(booleans={false,true}) void validCompletedSetIsNeverRequeuedByRetry(boolean sqlite){var f=fixture(sqlite);var set=f.store.request(f.course,"hash","key","title",Map.of(),false);var result=Map.<String,Object>of("questions",List.of(Map.of("id","valid")));f.store.complete(f.store.claim(set.id()).orElseThrow(),result);var retried=f.store.request(f.course,"hash","key","title",Map.of(),true);assertEquals("completed",retried.status());assertEquals(result,retried.result());assertTrue(f.store.claim(set.id()).isEmpty());}
 @ParameterizedTest @ValueSource(booleans={false,true}) void concurrentEmptyRetriesClaimOnlyOneGeneration(boolean sqlite)throws Exception{
  var f=fixture(sqlite);var set=f.store.request(f.course,"hash","key","title",Map.of(),false);f.store.complete(f.store.claim(set.id()).orElseThrow(),Map.of("questions",List.of()));
  var pool=Executors.newFixedThreadPool(4);var claims=new AtomicInteger();try{var futures=new ArrayList<Future<?>>();for(int i=0;i<16;i++)futures.add(pool.submit(()->{var retry=f.store.request(f.course,"hash","key","title",Map.of(),true);assertEquals(set.id(),retry.id());if(f.store.claim(retry.id()).isPresent())claims.incrementAndGet();}));for(var future:futures)future.get(20,TimeUnit.SECONDS);}finally{pool.shutdownNow();}
  assertEquals(1,claims.get());assertEquals(1,f.jdbc.queryForObject("SELECT COUNT(*) FROM practice_sets",Integer.class));assertEquals(1,f.jdbc.queryForObject("SELECT attempt_count FROM practice_sets",Integer.class));
 }
}

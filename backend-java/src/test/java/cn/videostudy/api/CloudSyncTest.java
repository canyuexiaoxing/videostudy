package cn.videostudy.api;
import cn.videostudy.cloud.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import java.nio.file.Path;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
class CloudSyncTest {
 @TempDir Path folder;final ObjectMapper json=new ObjectMapper();
 JdbcTemplate cloud(){var ds=new DriverManagerDataSource("jdbc:h2:mem:"+UUID.randomUUID()+";MODE=MySQL;DB_CLOSE_DELAY=-1","sa","");var files=new org.springframework.core.io.support.PathMatchingResourcePatternResolver();try{var resources=files.getResources("classpath:db/migration/V*.sql");Arrays.sort(resources,Comparator.comparingInt(r->Integer.parseInt(r.getFilename().substring(1,r.getFilename().indexOf('_')))));for(var resource:resources){if(resource.getFilename().startsWith("V16__")){new ResourceDatabasePopulator(new org.springframework.core.io.ByteArrayResource(new String(resource.getInputStream().readAllBytes(),java.nio.charset.StandardCharsets.UTF_8).replace(", ADD COLUMN", "; ALTER TABLE transcription_jobs ADD COLUMN").getBytes(java.nio.charset.StandardCharsets.UTF_8))).execute(ds);}else new ResourceDatabasePopulator(resource).execute(ds);}}catch(Exception e){throw new IllegalStateException(e);}return new JdbcTemplate(ds);}
 CourseSnapshotStore.Snapshot snapshot(JdbcTemplate jdbc,String id,String name){new TranscriptionJobStore(jdbc,json).createQueued(id);jdbc.update("UPDATE transcription_jobs SET status='completed',original_filename=? WHERE id=?",name,id);return new CourseSnapshotStore(jdbc,json).exportCourse(id);}
 @Test void authenticationRevisionConflictAndIdempotentRetry()throws Exception{
  var store=new CloudDocumentStore(cloud(),json);var mvc=MockMvcBuilders.standaloneSetup(new CloudSyncController(store,"t".repeat(64),"owner")).build();mvc.perform(get("/api/cloud-sync/health")).andExpect(status().isUnauthorized());mvc.perform(get("/api/cloud-sync/health").header("X-Framewise-Sync","wrong")).andExpect(status().isUnauthorized());mvc.perform(get("/api/cloud-sync/health").header("X-Framewise-Sync","t".repeat(64))).andExpect(status().isOk());
  var jdbc=new JdbcTemplate(SQLiteStoreTest.database(folder.resolve("a.db")));String id=UUID.randomUUID().toString();var first=snapshot(jdbc,id,"lesson");assertEquals(1,store.put("owner",id,0,first).revision());assertEquals(1,store.put("owner",id,0,first).revision());jdbc.update("UPDATE transcription_jobs SET original_filename='changed' WHERE id=?",id);var changed=new CourseSnapshotStore(jdbc,json).exportCourse(id);assertThrows(IllegalArgumentException.class,()->store.put("owner",id,0,changed));assertEquals(2,store.put("owner",id,1,changed).revision());assertEquals(2,store.get("owner",id).revision());assertThrows(IllegalArgumentException.class,()->store.get("other",id));
 }
 @Test void noCloudConnectionOccursUntilExplicitlyRequestedAndOfflineDoesNotBreakLocal(){var jdbc=new JdbcTemplate(SQLiteStoreTest.database(folder.resolve("offline.db")));String id=UUID.randomUUID().toString();snapshot(jdbc,id,"offline");var service=new LocalSyncService(jdbc,json,"http://127.0.0.1:1","t".repeat(64));assertEquals(1,service.status().get("localCourses"));assertThrows(IllegalArgumentException.class,service::connect);assertEquals(1,new TranscriptionJobStore(jdbc,json).listHistory().size());}
 @Test void twoLocalDatabasesExchangeOverHttpAndProtectBothSides()throws Exception{
  var cloudStore=new CloudDocumentStore(cloud(),json);var server=com.sun.net.httpserver.HttpServer.create(new java.net.InetSocketAddress("127.0.0.1",0),0);
  server.createContext("/api/cloud-sync",exchange->{try{String suffix=exchange.getRequestURI().getPath().substring("/api/cloud-sync".length());Object body;if(!"t".repeat(64).equals(exchange.getRequestHeaders().getFirst("X-Framewise-Sync"))){exchange.sendResponseHeaders(401,-1);return;}if(suffix.equals("/health"))body=Map.of("status","ok","storage","mysql");else if(suffix.equals("/documents"))body=cloudStore.list("owner");else{String id=suffix.substring("/documents/".length());if(exchange.getRequestMethod().equals("PUT")){var upload=json.readValue(exchange.getRequestBody(),CloudSyncController.Upload.class);body=cloudStore.put("owner",id,upload.expectedRevision(),upload.snapshot());}else body=cloudStore.get("owner",id);}byte[] bytes=json.writeValueAsBytes(body);exchange.getResponseHeaders().set("Content-Type","application/json");exchange.sendResponseHeaders(200,bytes.length);exchange.getResponseBody().write(bytes);}catch(Exception e){exchange.sendResponseHeaders(409,-1);}finally{exchange.close();}});server.start();
  try{String url="http://127.0.0.1:"+server.getAddress().getPort();var a=new JdbcTemplate(SQLiteStoreTest.database(folder.resolve("client-a.db")));var b=new JdbcTemplate(SQLiteStoreTest.database(folder.resolve("client-b.db")));String id=UUID.randomUUID().toString();snapshot(a,id,"original");var first=new LocalSyncService(a,json,url,"t".repeat(64));var second=new LocalSyncService(b,json,url,"t".repeat(64));assertEquals(true,first.connect().get("connected"));first.push(id);first.push(id);second.pull(id);assertEquals("original",new TranscriptionJobStore(b,json).listHistory().getFirst().name());
   a.update("UPDATE transcription_jobs SET original_filename='changed on A' WHERE id=?",id);first.push(id);b.update("UPDATE transcription_jobs SET original_filename='changed on B' WHERE id=?",id);assertEquals("local_changes",assertThrows(IllegalArgumentException.class,()->second.pull(id)).getMessage());assertEquals("sync_conflict",assertThrows(IllegalArgumentException.class,()->second.push(id)).getMessage());assertEquals("changed on B",new TranscriptionJobStore(b,json).listHistory().getFirst().name());assertEquals(2,cloudStore.get("owner",id).revision());
  }finally{server.stop(0);}
 }

}

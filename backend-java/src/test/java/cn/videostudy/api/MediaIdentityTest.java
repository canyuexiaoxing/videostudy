package cn.videostudy.api;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
class MediaIdentityTest {
 @TempDir Path directory;
 @Test void matchesFrontendAlgorithmIncludingOverlappingSamples()throws Exception{
  for(int length:new int[]{0,3,65535,65536,100000,200000}){
   byte[] data=new byte[length];new Random(123).nextBytes(data);Path file=directory.resolve("sample");Files.write(file,data);
   var digest=MessageDigest.getInstance("SHA-256");digest.update(java.nio.ByteBuffer.allocate(8).putLong(length).array());digest.update(Arrays.copyOfRange(data,0,Math.min(length,65536)));digest.update(Arrays.copyOfRange(data,Math.max(0,length-65536),length));
   assertEquals(new MediaIdentity(length,HexFormat.of().formatHex(digest.digest())),MediaIdentity.read(file));
  }
 }
 @Test void identityIsDurableInDatabaseAfterOriginalCleanup()throws Exception{
  var ds=new org.springframework.jdbc.datasource.DriverManagerDataSource("jdbc:h2:mem:"+UUID.randomUUID()+";MODE=MySQL;DB_CLOSE_DELAY=-1","sa","");
  new org.springframework.jdbc.datasource.init.ResourceDatabasePopulator(new org.springframework.core.io.ClassPathResource("db/migration/V1__create_transcription_jobs.sql")).execute(ds);
  var jdbc=new org.springframework.jdbc.core.JdbcTemplate(ds);
  // H2 does not accept the MySQL migration's multiple ADD COLUMN syntax.
  jdbc.execute("ALTER TABLE transcription_jobs ADD COLUMN media_size BIGINT NULL");jdbc.execute("ALTER TABLE transcription_jobs ADD COLUMN media_fingerprint VARCHAR(64) NULL");var store=new TranscriptionJobStore(jdbc,new com.fasterxml.jackson.databind.ObjectMapper());String id=UUID.randomUUID().toString();jdbc.update("INSERT INTO transcription_jobs(id,status) VALUES (?,'completed')",id);
  assertNull(store.findMediaIdentity(id));Files.writeString(directory.resolve("original"),"abc");var identity=MediaIdentity.read(directory.resolve("original"));store.saveMediaIdentity(id,identity);Files.delete(directory.resolve("original"));
  assertEquals(identity,new TranscriptionJobStore(jdbc,new com.fasterxml.jackson.databind.ObjectMapper()).findMediaIdentity(id));
 }
 @Test void migratesOnlyAutomaticCacheAndNeverOverwritesCanonicalIdentity()throws Exception{
  var store=mock(TranscriptionJobStore.class);String id=UUID.randomUUID().toString();when(store.find(id)).thenReturn(Optional.of(new TranscriptionController.TranscriptionJob(id,"completed",null,null)));
  var controller=new TranscriptionController(directory.toString(),"full",store,mock(MediaAnalyzer.class));String fp="a".repeat(64);var identity=new MediaIdentity(123,fp);
  try{
   assertEquals(400,controller.migrateMedia(id,new TranscriptionController.CachedMedia(123,fp,"user_confirmed")).getStatusCode().value());
   when(store.findMediaIdentity(id)).thenReturn(null,identity);assertEquals(200,controller.migrateMedia(id,new TranscriptionController.CachedMedia(123,fp,"legacy_auto")).getStatusCode().value());verify(store).migrateMediaIdentity(id,identity);
   when(store.findMediaIdentity(id)).thenReturn(identity);assertEquals(409,controller.migrateMedia(id,new TranscriptionController.CachedMedia(123,"b".repeat(64),"legacy_auto")).getStatusCode().value());verify(store,never()).saveMediaIdentity(anyString(),any());
  }finally{controller.close();}
 }
 @Test void legacyOriginalIsBackfilledAndMissingOriginalCannotBeManuallyBound()throws Exception{
  var store=mock(TranscriptionJobStore.class);String id=UUID.randomUUID().toString();
  when(store.find(id)).thenReturn(Optional.of(new TranscriptionController.TranscriptionJob(id,"completed",null,null)));
  var controller=new TranscriptionController(directory.toString(),"full",store,mock(MediaAnalyzer.class));
  try{
   assertEquals(410,controller.media(id).getStatusCode().value());verify(store,never()).saveMediaIdentity(anyString(),any());
   Files.writeString(directory.resolve(id),"abc");assertEquals(200,controller.media(id).getStatusCode().value());verify(store).saveMediaIdentity(eq(id),eq(MediaIdentity.read(directory.resolve(id))));
   var saved=MediaIdentity.read(directory.resolve(id));when(store.findMediaIdentity(id)).thenReturn(saved);Files.delete(directory.resolve(id));assertEquals(saved,controller.media(id).getBody());
   assertEquals(404,controller.media("../invalid").getStatusCode().value());
  }finally{controller.close();}
 }
}

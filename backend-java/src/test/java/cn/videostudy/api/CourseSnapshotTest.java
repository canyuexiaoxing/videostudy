package cn.videostudy.api;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.jdbc.core.JdbcTemplate;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.Path;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
class CourseSnapshotTest {
 @TempDir Path folder;
 @Test void roundTripPreservesCourseAndChatWithoutExportingPrivateTokens(){
  var a=new JdbcTemplate(SQLiteStoreTest.database(folder.resolve("a.db")));var b=new JdbcTemplate(SQLiteStoreTest.database(folder.resolve("b.db")));var json=new ObjectMapper();String id=UUID.randomUUID().toString();var main=new TranscriptionJobStore(a,json);main.createQueued(id);a.update("UPDATE transcription_jobs SET status='completed',result_json=? WHERE id=?","{\"language\":\"zh\",\"segments\":[]}",id);new SubtitleJobStore(a,json).request(id,"en",false);a.update("UPDATE subtitle_jobs SET status='failed'");var snapshot=new CourseSnapshotStore(a,json).exportCourse(id);assertFalse(json.valueToTree(snapshot).toString().contains(new SubtitleJobStore(a,json).callbackToken(id)));
  var store=new CourseSnapshotStore(b,json);store.restore(snapshot,null);assertEquals("completed",new TranscriptionJobStore(b,json).find(id).orElseThrow().status());assertEquals(1,b.queryForObject("SELECT COUNT(*) FROM subtitle_jobs",Integer.class));assertEquals(CourseSnapshotStore.hash(json,snapshot),CourseSnapshotStore.hash(json,store.exportCourse(id)));
 }
 @Test void invalidCrossCourseRowsRollbackAndDirtyLocalCannotBeOverwritten(){
  var jdbc=new JdbcTemplate(SQLiteStoreTest.database(folder.resolve("test.db")));var json=new ObjectMapper();String id=UUID.randomUUID().toString();new TranscriptionJobStore(jdbc,json).createQueued(id);jdbc.update("UPDATE transcription_jobs SET status='completed' WHERE id=?",id);var store=new CourseSnapshotStore(jdbc,json);var snapshot=store.exportCourse(id);assertThrows(IllegalArgumentException.class,()->store.restore(snapshot,null));var rows=new LinkedHashMap<>(snapshot.tables());rows.put("overview_jobs",List.of(Map.of("transcription_id",UUID.randomUUID().toString(),"status","completed","attempt_count","0")));var wrong=new CourseSnapshotStore.Snapshot(1,id,rows);assertThrows(IllegalArgumentException.class,()->store.restore(wrong,CourseSnapshotStore.hash(json,snapshot)));assertEquals(1,jdbc.queryForObject("SELECT COUNT(*) FROM transcription_jobs",Integer.class));
 }
}

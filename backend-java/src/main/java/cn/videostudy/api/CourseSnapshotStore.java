package cn.videostudy.api;
import com.fasterxml.jackson.databind.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import java.util.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
/** Fixed relational graph; no client-supplied table or SQL identifiers are executed. */
public final class CourseSnapshotStore {
 public record Snapshot(int version,String courseId,Map<String,List<Map<String,Object>>> tables){}
 public static final List<String> TABLES=List.of("transcription_jobs","subtitle_sources","subtitle_jobs","chapter_jobs","overview_jobs","practice_sets","practice_sessions","practice_answers","question_chat_threads","question_chat_turns","overview_chat_threads","overview_chat_turns");
 private final JdbcTemplate jdbc;private final ObjectMapper json;private final TransactionTemplate tx;
 public CourseSnapshotStore(JdbcTemplate jdbc,ObjectMapper json){this.jdbc=jdbc;this.json=json;tx=new TransactionTemplate(new DataSourceTransactionManager(Objects.requireNonNull(jdbc.getDataSource())));}
 private String condition(String table){return switch(table){
  case "transcription_jobs"->"id=?";
  case "practice_sessions","question_chat_threads"->"set_id IN (SELECT id FROM practice_sets WHERE transcription_id=?)";
  case "practice_answers"->"session_id IN (SELECT id FROM practice_sessions WHERE set_id IN (SELECT id FROM practice_sets WHERE transcription_id=?))";
  case "question_chat_turns"->"thread_id IN (SELECT id FROM question_chat_threads WHERE set_id IN (SELECT id FROM practice_sets WHERE transcription_id=?))";
  case "overview_chat_turns"->"thread_id IN (SELECT id FROM overview_chat_threads WHERE transcription_id=?)";
  default->"transcription_id=?";};}
 private List<Map<String,Object>> rows(String table,String id){
  return jdbc.query("SELECT * FROM "+table+" WHERE "+condition(table), (r,n)->{var row=new TreeMap<String,Object>();var meta=r.getMetaData();for(int i=1;i<=meta.getColumnCount();i++){String column=meta.getColumnName(i).toLowerCase(Locale.ROOT);if(column.equals("callback_token"))continue;Object value=r.getString(i);if(column.equals("lock_until")&&r.getLong(i)>System.currentTimeMillis())throw new IllegalArgumentException("course_busy");if(column.equals("run_token")||column.equals("lock_token"))value=null;if(column.equals("lock_until"))value="0";if(value!=null&&Set.of("created_at","updated_at","next_attempt_at").contains(column))value=r.getTimestamp(i).toLocalDateTime().format(java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss.SSS"));row.put(column,value);}return (Map<String,Object>)row;},id).stream().sorted(Comparator.comparing(row->encode(json,row))).toList();
 }
 public Snapshot exportCourse(String id){validId(id);return tx.execute(status->{var tables=new LinkedHashMap<String,List<Map<String,Object>>>();for(String table:TABLES){var records=rows(table,id);for(var row:records)if(Set.of("queued","processing","awaiting_source").contains(Objects.toString(row.get("status"),""))||Long.parseLong(Objects.toString(row.get("lock_until"),"0"))>System.currentTimeMillis())throw new IllegalArgumentException("course_busy");tables.put(table,records);}if(tables.get("transcription_jobs").size()!=1)throw new IllegalArgumentException("course_not_found");var result=new Snapshot(1,id,tables);validate(result);return result;});}
 public static void validId(String id){try{if(!UUID.fromString(id).toString().equalsIgnoreCase(id))throw new IllegalArgumentException();}catch(Exception e){throw new IllegalArgumentException("invalid_course_id");}}
 public static void validate(Snapshot snapshot){
  if(snapshot==null||snapshot.version()!=1||snapshot.tables()==null||!new HashSet<>(TABLES).equals(snapshot.tables().keySet()))throw new IllegalArgumentException("invalid_snapshot");validId(snapshot.courseId());var root=snapshot.tables().get("transcription_jobs");if(root==null||root.size()!=1||!snapshot.courseId().equals(root.getFirst().get("id")))throw new IllegalArgumentException("invalid_snapshot");
  var ids=new HashMap<String,Set<String>>();for(String table:TABLES){var records=snapshot.tables().get(table);if(records==null||records.size()>50000)throw new IllegalArgumentException("invalid_snapshot");var set=new HashSet<String>();for(var row:records){if(row==null||row.size()>40||row.values().stream().anyMatch(v->v!=null&&!(v instanceof String)))throw new IllegalArgumentException("invalid_snapshot");if(row.containsKey("id")){String id=Objects.toString(row.get("id"),"");validId(id);if(!set.add(id))throw new IllegalArgumentException("invalid_snapshot");}String parent=switch(table){case "practice_sessions","question_chat_threads"->"set_id";case "practice_answers"->"session_id";case "question_chat_turns","overview_chat_turns"->"thread_id";case "transcription_jobs"->null;default->"transcription_id";};if(parent!=null){String expected=switch(table){case "practice_sessions","question_chat_threads"->"practice_sets";case "practice_answers"->"practice_sessions";case "question_chat_turns"->"question_chat_threads";case "overview_chat_turns"->"overview_chat_threads";default->"transcription_jobs";};if(!ids.getOrDefault(expected,Set.of()).contains(row.get(parent)))throw new IllegalArgumentException("invalid_snapshot");}if(Set.of("queued","processing","awaiting_source").contains(Objects.toString(row.get("status"),"")))throw new IllegalArgumentException("course_busy");}ids.put(table,set);}
 }
 public void restore(Snapshot snapshot,String expectedLocalHash){validate(snapshot);tx.executeWithoutResult(status->{String id=snapshot.courseId();boolean exists=jdbc.queryForObject("SELECT COUNT(*) FROM transcription_jobs WHERE id=?",Integer.class,id)>0;if(exists&&(expectedLocalHash==null||!hash(json,exportCourse(id)).equals(expectedLocalHash)))throw new IllegalArgumentException("local_changes");if(!exists&&expectedLocalHash!=null)throw new IllegalArgumentException("local_changes");
  // Check all column names before deleting any local rows, then let FK constraints validate the graph atomically.
  for(String table:TABLES){Set<String> columns=jdbc.query("SELECT * FROM "+table+" WHERE 1=0",r->{var result=new HashSet<String>();var meta=r.getMetaData();for(int i=1;i<=meta.getColumnCount();i++)result.add(meta.getColumnName(i).toLowerCase(Locale.ROOT));return result;});for(var row:snapshot.tables().get(table))if(!columns.containsAll(row.keySet()))throw new IllegalArgumentException("invalid_snapshot");}
  if(exists)jdbc.update("DELETE FROM transcription_jobs WHERE id=?",id);
  for(String table:TABLES)for(var saved:snapshot.tables().get(table)){var row=new LinkedHashMap<>(saved);if(table.equals("subtitle_sources"))row.put("callback_token",UUID.randomUUID().toString().replace("-","")+UUID.randomUUID().toString().replace("-",""));if(row.containsKey("run_token"))row.put("run_token",null);if(row.containsKey("lock_token"))row.put("lock_token",null);if(row.containsKey("lock_until"))row.put("lock_until","0");jdbc.update("INSERT INTO "+table+" ("+String.join(",",row.keySet())+") VALUES ("+String.join(",",Collections.nCopies(row.size(),"?"))+")",row.values().toArray());}
 });}
 private static String encode(ObjectMapper json,Object value){try{return json.copy().enable(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS).writeValueAsString(value);}catch(Exception e){throw new IllegalArgumentException("invalid_snapshot");}}
 public static String hash(ObjectMapper json,Snapshot snapshot){try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(encode(json,snapshot).getBytes(StandardCharsets.UTF_8)));}catch(Exception e){throw new IllegalArgumentException("invalid_snapshot");}}
}

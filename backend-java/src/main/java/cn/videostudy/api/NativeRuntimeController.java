package cn.videostudy.api;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.Set;

@RestController
@RequestMapping("/api/runtime")
public class NativeRuntimeController {
 private static final org.slf4j.Logger log=org.slf4j.LoggerFactory.getLogger(NativeRuntimeController.class);
 private final JdbcTemplate jdbc;private final PreviewActivity activity;private final ObjectMapper json;private final Path conversions;private final boolean nativeEnabled;private final Runnable shutdown;private final java.util.concurrent.atomic.AtomicBoolean stopping=new java.util.concurrent.atomic.AtomicBoolean();
 @org.springframework.beans.factory.annotation.Autowired
 public NativeRuntimeController(JdbcTemplate jdbc,PreviewActivity activity,ObjectMapper json,@Value("${media.temp-dir}") String directory,@Value("${FRAMEWISE_RUNTIME_TOKEN:}") String token,org.springframework.context.ConfigurableApplicationContext context){this(jdbc,activity,json,directory,token,()->org.springframework.boot.SpringApplication.exit(context));}
 NativeRuntimeController(JdbcTemplate jdbc,PreviewActivity activity,ObjectMapper json,String directory,String token,Runnable shutdown){this.jdbc=jdbc;this.activity=activity;this.json=json;conversions=Path.of(directory).resolve("compatibility");nativeEnabled=token!=null&&!token.isEmpty();this.shutdown=shutdown;}
 public NativeRuntimeController(JdbcTemplate jdbc,PreviewActivity activity,ObjectMapper json,String directory){this(jdbc,activity,json,directory,"",()->{});}
 @GetMapping("/health") public ResponseEntity<Map<String,Object>> health(){if(!nativeEnabled)return ResponseEntity.notFound().build();return ResponseEntity.ok(Map.of("status","ready","storage",DatabaseDialect.sqlite(jdbc)?"sqlite":"mysql","role","local","protocolVersion",1));}
 @GetMapping("/activity") public ResponseEntity<Map<String,Object>> activity(){
  if(!nativeEnabled)return ResponseEntity.notFound().build();
  long started=System.nanoTime();
  try {
   int active=0;
   for(String table:List.of("transcription_jobs","overview_jobs","chapter_jobs","subtitle_jobs","practice_sets"))active+=jdbc.queryForObject("SELECT COUNT(*) FROM "+table+" WHERE status IN ('queued','processing','awaiting_source')",Integer.class);
   for(String table:List.of("question_chat_threads","overview_chat_threads"))active+=jdbc.queryForObject("SELECT COUNT(*) FROM "+table+" WHERE lock_until>?",Integer.class,System.currentTimeMillis());
   if(activity.busy())active++;
   active+=conversionCount();
   return ResponseEntity.ok(Map.of("activeJobs",active,"busy",active>0));
  }catch(Exception error){log.warn("Native runtime request={} stage=activity result=failed error_type={} elapsed_ms={}",java.util.UUID.randomUUID(),error.getClass().getSimpleName(),(System.nanoTime()-started)/1000000);return ResponseEntity.status(503).body(Map.of("activeJobs",1,"busy",true,"error","activity_unavailable"));}
 }
 @PostMapping("/shutdown") public ResponseEntity<Map<String,Object>> shutdown(){
  if(!nativeEnabled)return ResponseEntity.notFound().build();
  if(stopping.compareAndSet(false,true)){
   String request=java.util.UUID.randomUUID().toString();
   log.info("Native runtime request={} stage=shutdown result=accepted",request);
   java.util.concurrent.CompletableFuture.runAsync(()->{long started=System.nanoTime();try{shutdown.run();log.info("Native runtime request={} stage=shutdown result=completed elapsed_ms={}",request,(System.nanoTime()-started)/1000000);}catch(Exception error){log.warn("Native runtime request={} stage=shutdown result=failed error_type={} elapsed_ms={}",request,error.getClass().getSimpleName(),(System.nanoTime()-started)/1000000);}},java.util.concurrent.CompletableFuture.delayedExecutor(150,java.util.concurrent.TimeUnit.MILLISECONDS));
  }
  return ResponseEntity.accepted().body(Map.of("status","stopping"));
 }
 private int conversionCount()throws java.io.IOException {
  if(!Files.exists(conversions))return 0;
  int count=0;try(var paths=Files.list(conversions)){
   var folders=paths.filter(Files::isDirectory).limit(1001).toList();if(folders.size()>1000)return 1;
   for(Path folder:folders){Path status=folder.resolve("status.json");if(!Files.isRegularFile(status)||!Set.of("completed","failed","cancelled").contains(json.readTree(Files.readString(status)).path("status").asText()))count++;}
  }return count;
 }
}

package cn.videostudy.api;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/** Read-only permission lease. Thumbnail decoding and storage remain on the user's device. */
@RestController
@RequestMapping("/api/transcriptions")
@CrossOrigin(origins={"http://localhost:5173","http://127.0.0.1:5173","app://videostudy"})
public class PreviewGateController {
 private static final org.slf4j.Logger log=org.slf4j.LoggerFactory.getLogger(PreviewGateController.class);
 private final JdbcTemplate jdbc;private final TranscriptionJobStore main;private final ObjectMapper json;private final Path uploads;private final PreviewActivity activity;
 private final Map<String,String> last=new ConcurrentHashMap<>();
 public record Permission(boolean allowed,String reason,int leaseMs){}
 public PreviewGateController(JdbcTemplate jdbc,TranscriptionJobStore main,ObjectMapper json,@Value("${media.temp-dir}") String directory,PreviewActivity activity){this.jdbc=jdbc;this.main=main;this.json=json;this.uploads=Path.of(directory).resolve("compatibility");this.activity=activity;}
 @GetMapping("/{id}/preview-permission") public Permission check(@PathVariable String id){
  long started=System.nanoTime();String reason="idle";
  try {
   if(!SubtitleController.validId(id))return new Permission(false,"invalid_job_id",0);
   var job=main.find(id).orElse(null);
   if(job==null||!"completed".equals(job.status())||job.result()==null||job.result().mindMap()==null||!"completed".equals(job.result().mindMap().status()))reason="map_not_completed";
   else if(jdbc.queryForObject("SELECT COUNT(*) FROM overview_jobs WHERE transcription_id=? AND status='completed'",Integer.class,id)!=1)reason="overview_not_completed";
   else if(activity.busy())reason="foreground_request";
   else {
    for(var table:List.of("transcription_jobs","overview_jobs","chapter_jobs","subtitle_jobs","practice_sets")){
     if(jdbc.queryForObject("SELECT COUNT(*) FROM "+table+" WHERE status IN ('queued','processing')",Integer.class)>0){reason="foreground_job";break;}
    }
    if(reason.equals("idle")&&jdbc.queryForObject("SELECT COUNT(*) FROM question_chat_threads WHERE lock_until>?",Integer.class,System.currentTimeMillis())>0)reason="foreground_chat";
    if(reason.equals("idle")&&conversionBusy())reason="foreground_conversion";
   }
  } catch(Exception error){reason="idle_check_unavailable";}
  if(last.size()>256)last.clear();
  var previous=last.put(id,reason);
  if(!reason.equals(previous))log.info("Preview permission task={} stage=idle_check result={} elapsed_ms={}",id,reason,(System.nanoTime()-started)/1000000);
  return new Permission(reason.equals("idle"),reason,reason.equals("idle")?2000:0);
 }
 private boolean conversionBusy()throws java.io.IOException{
  if(!Files.exists(uploads))return false;
  try(var paths=Files.list(uploads)){
   var folders=paths.filter(Files::isDirectory).limit(1001).toList();if(folders.size()>1000)return true;
   for(var folder:folders){var state=folder.resolve("status.json");if(!Files.isRegularFile(state))return true;var status=json.readTree(Files.readString(state)).path("status").asText();if(!Set.of("completed","failed","cancelled").contains(status))return true;}
  }return false;
 }
}

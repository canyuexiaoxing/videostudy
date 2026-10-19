package cn.videostudy.api;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.core.type.TypeReference;
import java.util.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

@RestController
@RequestMapping("/api/transcriptions/{course}/overview/chat")
@CrossOrigin(origins={"http://localhost:5173","http://127.0.0.1:5173"})
public class OverviewChatController {
 private static final org.slf4j.Logger log=org.slf4j.LoggerFactory.getLogger(OverviewChatController.class);
 private final JdbcTemplate jdbc;private final ObjectMapper json;private final TranscriptionJobStore main;private final OverviewChatStore chats;private final MediaAnalyzer agent;
 public OverviewChatController(JdbcTemplate jdbc,ObjectMapper json,TranscriptionJobStore main,OverviewChatStore chats,MediaAnalyzer agent){this.jdbc=jdbc;this.json=json;this.main=main;this.chats=chats;this.agent=agent;}
 public record Request(String contextKey,String requestId,String message){}
 record Context(String key,Map<String,Object> overview,TranscriptionController.TranscriptResult source){}
 private Context context(String course){
  var job=main.find(course).orElseThrow(()->new IllegalArgumentException("course_not_found"));
  if(!"completed".equals(job.status())||job.result()==null)throw new IllegalArgumentException("course_not_completed");
  var results=jdbc.query("SELECT result_json FROM overview_jobs WHERE transcription_id=? AND status='completed'",(r,n)->r.getString(1),course);
  if(results.isEmpty()||results.getFirst()==null)return null;
  try{var overview=json.readValue(results.getFirst(),new TypeReference<Map<String,Object>>(){});if(!"completed".equals(overview.get("status")))return null;
   String key=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(results.getFirst().getBytes(StandardCharsets.UTF_8)));return new Context(key,overview,job.result());
  }catch(Exception error){throw new IllegalStateException("Invalid overview context",error);}
 }
 private static void ids(String...ids){for(var id:ids)if(id==null||!SubtitleController.validId(id))throw new IllegalArgumentException("invalid_chat_id");}
 @GetMapping public Map<String,Object> history(@PathVariable String course,@RequestHeader("X-Study-Client") String client){
  ids(course,client);var context=context(course);if(context==null)return Map.of("status","not_ready","messages",List.of());
  return Map.of("status","ready","contextKey",context.key(),"contextMode",context.overview().containsKey("conversationId")?"original":"restored","messages",chats.history(chats.thread(course,context.key(),client)));
 }
 @PostMapping public ResponseEntity<?> send(@PathVariable String course,@RequestHeader("X-Study-Client") String client,@RequestBody Request request){
  ids(course,client,request.requestId());
  if(request.message()==null||request.message().isBlank()||request.message().length()>2000)throw new IllegalArgumentException("invalid_chat_message");
  var context=context(course);if(context==null)return ResponseEntity.status(409).body(Map.of("error","overview_not_completed"));
  if(!context.key().equals(request.contextKey()))return ResponseEntity.status(409).body(Map.of("error","overview_context_changed"));
  String thread=chats.thread(course,context.key(),client),message=request.message().trim();var previous=chats.previous(thread,request.requestId());if(previous.isPresent())return cached(previous.get(),message);
  String token=UUID.randomUUID().toString();if(!chats.claim(thread,token))return ResponseEntity.status(409).body(Map.of("error","chat_busy"));
  long started=System.nanoTime();log.info("overview_chat course={} request={} stage=started",course,request.requestId());
  try{
   previous=chats.previous(thread,request.requestId());if(previous.isPresent())return cached(previous.get(),message);
   if(chats.count(thread)>=40)return ResponseEntity.status(429).body(Map.of("error","chat_limit"));
   Map<String,Object> raw;
   try{raw=agent.chatOverview(Map.of("courseId",course,"overview",context.overview(),"source",context.source(),"history",chats.history(thread),"message",message));}
   catch(Exception error){log.warn("overview_chat course={} request={} stage=provider error={} elapsedMs={}",course,request.requestId(),error.getClass().getSimpleName(),(System.nanoTime()-started)/1_000_000);return ResponseEntity.status(502).body(Map.of("error","overview_chat_failed"));}
   var evidence=context.source().segments().stream().map(s->Map.<String,Object>of("sourceId",s.id(),"startMs",s.startMs(),"endMs",s.endMs(),"quote",s.text())).toList();
   Map<String,Object> reply;
   try{reply=new LinkedHashMap<>(QuestionChatController.validate(raw,Map.of("evidence",evidence)));if(("original".equals(raw.get("contextMode"))||"restored".equals(raw.get("contextMode"))))reply.put("contextMode",raw.get("contextMode"));}
   catch(IllegalArgumentException error){log.warn("overview_chat course={} request={} stage=validation error={} elapsedMs={}",course,request.requestId(),error.getClass().getSimpleName(),(System.nanoTime()-started)/1_000_000);return ResponseEntity.status(502).body(Map.of("error","invalid_chat_reply"));}
   var current=context(course);if(current==null||!current.key().equals(context.key()))return ResponseEntity.status(409).body(Map.of("error","overview_context_changed"));
   chats.save(thread,token,request.requestId(),message,reply);
   log.info("overview_chat course={} request={} stage=saved elapsedMs={}",course,request.requestId(),(System.nanoTime()-started)/1_000_000);
   return ResponseEntity.ok(reply);
  }finally{chats.release(thread,token);}
 }
 private static ResponseEntity<?> cached(Map<String,Object> stored,String message){if(!message.equals(stored.get("message")))return ResponseEntity.status(409).body(Map.of("error","chat_request_conflict"));var answer=new LinkedHashMap<>(stored);answer.remove("message");return ResponseEntity.ok(answer);}
 @ExceptionHandler(IllegalArgumentException.class) public ResponseEntity<?> invalid(IllegalArgumentException error){return ResponseEntity.badRequest().body(Map.of("error",error.getMessage()));}
}

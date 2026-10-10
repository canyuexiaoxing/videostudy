package cn.videostudy.api;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import java.util.*;

@RestController
@RequestMapping("/api/transcriptions/{course}/practice/{set}/questions/{question}/chat")
@CrossOrigin(origins={"http://localhost:5173","http://127.0.0.1:5173"})
public class QuestionChatController {
    private final QuestionChatStore chats;private final PracticeStore practice;private final MediaAnalyzer agent;
    public record Request(String sessionId,String requestId,String message){}
    public QuestionChatController(QuestionChatStore chats,PracticeStore practice,MediaAnalyzer agent){this.chats=chats;this.practice=practice;this.agent=agent;}
    private static void ids(String...ids){for(var id:ids)if(id==null||!SubtitleController.validId(id))throw new IllegalArgumentException("invalid_chat_id");}
    @GetMapping public List<Map<String,Object>> history(@PathVariable String course,@PathVariable String set,@PathVariable String question,
        @RequestHeader("X-Practice-Client") String client,@RequestParam String sessionId){
        ids(course,set,question,client,sessionId);practice.requireChatSession(course,set,sessionId,client,question);
        return chats.history(chats.thread(set,question,client));
    }
    @PostMapping public ResponseEntity<?> send(@PathVariable String course,@PathVariable String set,@PathVariable String question,
        @RequestHeader("X-Practice-Client") String client,@RequestBody Request request){
        ids(course,set,question,client,request.sessionId(),request.requestId());
        if(request.message()==null||request.message().isBlank()||request.message().length()>2000)throw new IllegalArgumentException("invalid_chat_message");
        var context=practice.chatContext(course,set,request.sessionId(),client,question);
        String thread=chats.thread(set,question,client);var existing=chats.previous(thread,request.requestId());
        if(existing.isPresent())return cached(existing.get(),request.message().trim());
        String token=UUID.randomUUID().toString();
        if(!chats.claim(thread,token))return ResponseEntity.status(409).body(Map.of("error","chat_busy"));
        try{
            existing=chats.previous(thread,request.requestId());if(existing.isPresent())return cached(existing.get(),request.message().trim());
            if(chats.count(thread)>=20)return ResponseEntity.status(429).body(Map.of("error","chat_limit"));
            var history=chats.history(thread);var recent=history.subList(Math.max(0,history.size()-12),history.size());
            Map<String,Object> reply;
            try{reply=validate(agent.chatQuestion(Map.of("context",context,"history",recent,"message",request.message().trim())),context);}
            catch(Exception error){return ResponseEntity.status(502).body(Map.of("error","chat_provider_failed"));}
            chats.save(thread,token,request.requestId(),request.message().trim(),reply);
            return ResponseEntity.ok(reply);
        }finally{chats.release(thread,token);}
    }
    private static ResponseEntity<?> cached(Map<String,Object> stored,String message){
        if(!message.equals(stored.get("message")))return ResponseEntity.status(409).body(Map.of("error","chat_request_conflict"));
        var reply=new LinkedHashMap<>(stored);reply.remove("message");return ResponseEntity.ok(reply);
    }
    @SuppressWarnings("unchecked") static Map<String,Object> validate(Map<String,Object> raw,Map<String,Object> context){
        if(raw==null||!(raw.get("reply") instanceof String reply)||reply.isBlank()||reply.length()>6000||!(raw.get("citations") instanceof List<?> citations)||citations.size()>3)throw new IllegalArgumentException("invalid_chat_reply");
        var sources=new HashMap<String,Map<String,Object>>();for(var ref:(List<Map<String,Object>>)context.get("evidence"))sources.put((String)ref.get("sourceId"),ref);
        var checked=new ArrayList<Map<String,Object>>();var seen=new HashSet<String>();
        for(var item:citations){if(!(item instanceof Map<?,?> ref)||!(ref.get("sourceId") instanceof String id)||!sources.containsKey(id))throw new IllegalArgumentException("invalid_chat_citation");
            var source=sources.get(id);
            for(String key:List.of("startMs","endMs"))if(!(ref.get(key) instanceof Number a)||!(source.get(key) instanceof Number b)||a.doubleValue()!=b.doubleValue())throw new IllegalArgumentException("invalid_chat_citation");
            if(!Objects.equals(source.get("quote"),ref.get("quote")))throw new IllegalArgumentException("invalid_chat_citation");
            if(seen.add(id))checked.add(source);
        }
        return Map.of("reply",reply.trim(),"citations",checked);
    }
    @ExceptionHandler(IllegalArgumentException.class) public ResponseEntity<?> invalid(IllegalArgumentException error){return ResponseEntity.badRequest().body(Map.of("error",error.getMessage()));}
}

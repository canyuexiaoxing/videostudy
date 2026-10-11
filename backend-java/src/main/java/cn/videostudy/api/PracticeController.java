package cn.videostudy.api;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PreDestroy;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.context.event.EventListener;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClientResponseException;
import java.util.*;
import java.util.concurrent.*;
import java.security.MessageDigest;
import java.nio.charset.StandardCharsets;
import static cn.videostudy.api.TranscriptionController.*;

@RestController
@RequestMapping("/api/transcriptions/{id}/practice")
@CrossOrigin(origins={"http://localhost:5173","http://127.0.0.1:5173"})
public class PracticeController {
    private final PracticeStore store;
    private final TranscriptionJobStore main;
    private final MediaAnalyzer agent;
    private final ObjectMapper json;
    private final ThreadPoolExecutor worker=new ThreadPoolExecutor(1,1,0,TimeUnit.MILLISECONDS,new ArrayBlockingQueue<>(4));
    private final Set<String> dispatched=ConcurrentHashMap.newKeySet();
    public record Request(String nodeId,int count,String difficulty,boolean retry) {}
    public record SessionRequest(boolean fresh) {}
    public record AnswerRequest(String questionId,int selectedIndex) {}
    public PracticeController(PracticeStore store,TranscriptionJobStore main,MediaAnalyzer agent,ObjectMapper json){this.store=store;this.main=main;this.agent=agent;this.json=json;}
    @GetMapping public ResponseEntity<?> list(@PathVariable String id){
        if(!SubtitleController.validId(id))return ResponseEntity.badRequest().build();
        if(main.find(id).isEmpty())return ResponseEntity.notFound().build();
        return ResponseEntity.ok(store.list(id));
    }
    @PostMapping public ResponseEntity<?> generate(@PathVariable String id,@RequestBody Request request){
        if(!SubtitleController.validId(id))return ResponseEntity.badRequest().build();
        var parent=main.find(id);if(parent.isEmpty())return ResponseEntity.notFound().build();
        if(!"completed".equals(parent.get().status()))return ResponseEntity.status(409).body(Map.of("error","course_not_completed"));
        try{
            var result=parent.get().result();var source=source(result,request);
            String hash=hash(json.writeValueAsString(result.mindMap()));
            String key=hash(hash+":"+source.get("scopeNodeId")+":"+json.writer().with(com.fasterxml.jackson.databind.SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS).writeValueAsString(source)+":mindmap-practice-v2");
            var set=store.request(id,hash,key,result.mindMap().root().id().equals(source.get("scopeNodeId"))?"整课知识点":(String)source.get("scopeTitle"),source,request.retry());
            dispatch();return ResponseEntity.accepted().body(store.publicSet(id,set.id()));
        }catch(IllegalArgumentException error){return ResponseEntity.unprocessableEntity().body(Map.of("error",error.getMessage()));}
        catch(Exception error){return ResponseEntity.status(500).body(Map.of("error","practice_request_failed"));}
    }
    @GetMapping("/{set}") public Map<String,Object> get(@PathVariable String id,@PathVariable String set){return store.publicSet(id,set);}
    @PostMapping("/{set}/sessions") public Map<String,Object> session(@PathVariable String id,@PathVariable String set,@RequestHeader("X-Practice-Client") String client,@RequestBody SessionRequest request){
        requireClient(client);store.publicSet(id,set);
        String session=request.fresh()?store.createSession(id,set,client):store.latestSession(set,client).orElseGet(()->store.createSession(id,set,client));
        return store.session(id,set,session,client);
    }
    @GetMapping("/{set}/sessions/{session}") public Map<String,Object> restore(@PathVariable String id,@PathVariable String set,@PathVariable String session,@RequestHeader("X-Practice-Client") String client){requireClient(client);return store.session(id,set,session,client);}
    @PostMapping("/{set}/sessions/{session}/answers") public Map<String,Object> answer(@PathVariable String id,@PathVariable String set,@PathVariable String session,@RequestHeader("X-Practice-Client") String client,@RequestBody AnswerRequest answer){requireClient(client);return store.answer(id,set,session,client,answer.questionId(),answer.selectedIndex());}
    @ExceptionHandler(IllegalArgumentException.class) public ResponseEntity<?> invalid(IllegalArgumentException error){return ResponseEntity.badRequest().body(Map.of("error",error.getMessage()));}
    private static void requireClient(String client){if(!SubtitleController.validId(client))throw new IllegalArgumentException("invalid_practice_client");}
    static MindMapNode find(MindMapNode node,String id){
        if(node.id().equals(id))return node;
        if(node.children()!=null)for(var child:node.children()){var found=find(child,id);if(found!=null)return found;}return null;
    }
    private static int leafCount(MindMapNode node) {
        if(node.children()==null||node.children().isEmpty())return 1;
        return node.children().stream().mapToInt(PracticeController::leafCount).sum();
    }
    private static boolean scopePath(MindMapNode node,String id,List<MindMapNode> path) {
        path.add(node);
        if(node.id().equals(id))return true;
        if(node.children()!=null)for(var child:node.children())if(scopePath(child,id,path))return true;
        path.removeLast();return false;
    }
    static MindMapNode practiceScope(MindMapNode root,String id) {
        if(id==null||id.isBlank())return root;
        var path=new ArrayList<MindMapNode>();
        if(!scopePath(root,id,path))throw new IllegalArgumentException("unknown_mindmap_node");
        for(int i=path.size()-1;i>0;i--){var node=path.get(i);if(node.children()!=null&&!node.children().isEmpty()&&leafCount(node)>1)return node;}
        return root;
    }
    private static void flatten(MindMapNode node,List<MindMapNode> nodes){
        if(node.children()!=null&&!node.children().isEmpty())node.children().forEach(child->flatten(child,nodes));
        else nodes.add(node);
    }
    static Map<String,Object> source(TranscriptResult result,Request request){
        if(!List.of(0,3,5,10).contains(request.count())||!List.of("basic","application","advanced").contains(Objects.toString(request.difficulty(),"")))throw new IllegalArgumentException("invalid_practice_settings");
        if(result.mindMap()==null||!"completed".equals(result.mindMap().status())||result.mindMap().root()==null)throw new IllegalArgumentException("mindmap_not_ready");
        var root=result.mindMap().root();var chosen=practiceScope(root,request.nodeId());
        if(chosen==null)throw new IllegalArgumentException("unknown_mindmap_node");
        var candidates=new ArrayList<MindMapNode>();flatten(chosen,candidates);
        var speech=new HashMap<String,TranscriptSegment>();result.segments().forEach(segment->speech.put(segment.id(),segment));
        var nodes=new ArrayList<Map<String,Object>>();
        for(var node:candidates){
            var refs=new ArrayList<Map<String,Object>>();
            if(node.evidenceRefs()!=null)for(var ref:node.evidenceRefs()){
                var segment=speech.get(ref.sourceId());if(segment!=null&&!segment.text().isBlank())refs.add(Map.of("sourceType","transcript","sourceId",segment.id(),"startMs",segment.startMs(),"endMs",segment.endMs(),"quote",segment.text()));
            }
            if(!refs.isEmpty())nodes.add(Map.of("id",node.id(),"title",node.title(),"evidenceRefs",refs));
        }
        if(nodes.isEmpty())throw new IllegalArgumentException("practice_evidence_missing");
        long first=Long.MAX_VALUE,last=0;
        for(var node:nodes)for(var ref:(List<Map<String,Object>>)node.get("evidenceRefs")){first=Math.min(first,((Number)ref.get("startMs")).longValue());last=Math.max(last,((Number)ref.get("endMs")).longValue());}
        // Keep only relevant page understanding; no images or repeated full transcript upload.
        var pages=new ArrayList<Map<String,Object>>();
        if(result.pageGroups()!=null)for(var page:result.pageGroups()){
            if(page.lastFrameTimeMs()<first||page.firstFrameTimeMs()>last)continue;
            var analysis=page.imageAnalysis();if(analysis==null||!"completed".equals(analysis.status()))analysis=page.textAnalysis();
            if(analysis!=null&&"completed".equals(analysis.status()))pages.add(Map.of("firstFrameTimeMs",page.firstFrameTimeMs(),"lastFrameTimeMs",page.lastFrameTimeMs(),"pageIndex",page.pageIndex(),"title",Objects.toString(analysis.title(),""),"content",Objects.toString(analysis.content(),"")));
            else if(page.ocrLines()!=null)pages.add(Map.of("firstFrameTimeMs",page.firstFrameTimeMs(),"lastFrameTimeMs",page.lastFrameTimeMs(),"pageIndex",page.pageIndex(),"ocr",page.ocrLines().stream().map(OcrLine::text).toList()));
        }
        return Map.of("scopeNodeId",chosen.id(),"scopeTitle",chosen.title(),"nodes",nodes,"pages",pages,"count",request.count()==0?Math.min(10,nodes.size()*2):request.count(),"difficulty",request.difficulty());
    }
    private static String hash(String value)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)));}
    @Scheduled(fixedDelay=2000) public void dispatch(){
        for(var id:store.due())if(dispatched.add(id))try{worker.execute(()->{try{process(id);}finally{dispatched.remove(id);}});}catch(RejectedExecutionException full){dispatched.remove(id);}
    }
    @EventListener(ApplicationReadyEvent.class) public void recover(){store.recover();dispatch();}
    private void process(String id){
        store.claim(id).ifPresent(run->{try{var result=agent.generatePractice(run.source());validate(result,run.source());store.complete(run,result);}
            catch(Exception error){boolean temporary=error instanceof ResourceAccessException||error instanceof RestClientResponseException r&&(r.getStatusCode().value()==429||r.getStatusCode().is5xxServerError());store.fail(run,"practice_generation_failed",temporary);}});
    }
    @SuppressWarnings("unchecked") static void validate(Map<String,Object> result,Map<String,Object> source){
        if(result==null||!List.of("completed","empty").contains(result.get("status"))||!(result.get("questions") instanceof List<?> questions)||questions.size()>((Number)source.get("count")).intValue())throw new IllegalArgumentException("invalid_practice_result");
        var nodes=new HashMap<String,Map<String,Object>>();((List<Map<String,Object>>)source.get("nodes")).forEach(n->nodes.put((String)n.get("id"),n));
        var ids=new HashSet<String>();
        for(var raw:questions){
            if(!(raw instanceof Map<?,?> q)||!(q.get("id") instanceof String id)||!SubtitleController.validId(id)||!ids.add(id)||!nodes.containsKey(q.get("nodeId")))throw new IllegalArgumentException("invalid_question");
            var kind=q.get("kind");if(!List.of("single","true_false").contains(kind)||!(q.get("options") instanceof List<?> options)||options.size()!=("single".equals(kind)?4:2)||options.stream().anyMatch(o->!(o instanceof String s)||s.isBlank())||new HashSet<>(options).size()!=options.size())throw new IllegalArgumentException("invalid_options");
            if(!(q.get("answerIndex") instanceof Number answer)||answer.doubleValue()!=answer.intValue()||answer.intValue()<0||answer.intValue()>=options.size())throw new IllegalArgumentException("invalid_answer");
            for(String field:List.of("prompt","title","explanation","takeaway"))if(!(q.get(field) instanceof String s)||s.isBlank())throw new IllegalArgumentException("missing_question_content");
            if(!(q.get("distractorReasons") instanceof List<?> reasons)||reasons.size()!=options.size())throw new IllegalArgumentException("invalid_reasons");
            for(int i=0;i<reasons.size();i++)if(!(reasons.get(i) instanceof String s)||i!=answer.intValue()&&s.isBlank())throw new IllegalArgumentException("invalid_reasons");
            var canonical=(List<Map<String,Object>>)nodes.get(q.get("nodeId")).get("evidenceRefs");
            if(!(q.get("citations") instanceof List<?> refs)||refs.isEmpty())throw new IllegalArgumentException("missing_citations");
            for(var ref:refs)if(!(ref instanceof Map<?,?> citation)||canonical.stream().noneMatch(c->Objects.equals(c.get("sourceId"),citation.get("sourceId"))&&Objects.equals(c.get("quote"),citation.get("quote"))&&citation.get("startMs") instanceof Number start&&citation.get("endMs") instanceof Number end&&start.longValue()==((Number)c.get("startMs")).longValue()&&end.longValue()==((Number)c.get("endMs")).longValue()))throw new IllegalArgumentException("ungrounded_citation");
            if(q.get("diagram")!=null&&(!(q.get("diagram") instanceof Map<?,?> diagram)||!List.of("bar","line","table","circuit").contains(diagram.get("kind"))||!(q.get("validation") instanceof Map<?,?> flags)||!Boolean.TRUE.equals(flags.get("diagramChecked"))))throw new IllegalArgumentException("unvalidated_diagram");
        }
    }
    @PreDestroy public void close(){worker.shutdownNow();}
}

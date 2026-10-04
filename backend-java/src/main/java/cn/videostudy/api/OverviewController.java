package cn.videostudy.api;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.core.type.TypeReference;
import jakarta.annotation.PreDestroy;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.context.event.EventListener;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClientResponseException;
import java.util.*;
import java.util.concurrent.*;

@RestController
@RequestMapping("/api/transcriptions/{id}/overview")
@CrossOrigin(origins={"http://localhost:5173","http://127.0.0.1:5173"})
public class OverviewController {
    private final JdbcTemplate jdbc;
    private final ObjectMapper json;
    private final TranscriptionJobStore main;
    private final MediaAnalyzer agent;
    private final ThreadPoolExecutor worker=new ThreadPoolExecutor(1,1,0,TimeUnit.MILLISECONDS,new ArrayBlockingQueue<>(4));
    private final Set<String> dispatched=ConcurrentHashMap.newKeySet();
    public record Job(String id,String status,Map<String,Object> result,String error) {}
    public OverviewController(JdbcTemplate jdbc,ObjectMapper json,TranscriptionJobStore main,MediaAnalyzer agent) {
        this.jdbc=jdbc;this.json=json;this.main=main;this.agent=agent;
    }
    @GetMapping public ResponseEntity<?> get(@PathVariable String id) {
        if (!SubtitleController.validId(id)) return ResponseEntity.badRequest().body(Map.of("error","invalid_job_id"));
        if (main.find(id).isEmpty()) return ResponseEntity.notFound().build();
        return ResponseEntity.ok(find(id));
    }
    @PostMapping public ResponseEntity<?> generate(@PathVariable String id) {
        if (!SubtitleController.validId(id)) return ResponseEntity.badRequest().body(Map.of("error","invalid_job_id"));
        var parent=main.find(id);
        if (parent.isEmpty()) return ResponseEntity.notFound().build();
        if (!"completed".equals(parent.get().status())) return ResponseEntity.status(409).body(Map.of("error","course_not_completed"));
        request(id);
        return ResponseEntity.accepted().body(find(id));
    }
    public void request(String id) {
        try { jdbc.update("INSERT INTO overview_jobs (transcription_id,status) VALUES (?,'queued')",id); }
        catch (DuplicateKeyException existing) { /* Reuse the existing job. */ }
        catch (DataIntegrityViolationException deleted) { return; }
        dispatch();
    }
    private Job find(String id) {
        return jdbc.query("SELECT status,result_json,error_code FROM overview_jobs WHERE transcription_id=?",(r,n)->{
            try { return new Job(id,r.getString(1),r.getString(2)==null?null:json.readValue(r.getString(2),new TypeReference<Map<String,Object>>(){}),r.getString(3)); }
            catch (Exception e) { throw new IllegalStateException("Invalid overview result",e); }
        },id).stream().findFirst().orElse(new Job(id,"not_requested",null,null));
    }
    @Scheduled(fixedDelay=2000) public void dispatch() {
        for (var id:jdbc.query("SELECT transcription_id FROM overview_jobs WHERE status='queued' AND attempt_count<3",(r,n)->r.getString(1))) {
            if (!dispatched.add(id)) continue;
            try { worker.execute(()->{try{process(id);}finally{dispatched.remove(id);}}); }
            catch (RejectedExecutionException full) { dispatched.remove(id); }
        }
    }
    @EventListener(ApplicationReadyEvent.class) public void recover() {
        jdbc.update("UPDATE overview_jobs SET status=CASE WHEN attempt_count<3 THEN 'queued' ELSE 'failed' END,run_token=NULL,error_code='overview_interrupted' WHERE status='processing'");
        dispatch();
    }
    private void process(String id) {
        var token=UUID.randomUUID().toString();
        if (jdbc.update("UPDATE overview_jobs SET status='processing',run_token=?,attempt_count=attempt_count+1 WHERE transcription_id=? AND status='queued' AND attempt_count<3",token,id)!=1) return;
        try {
            var parent=main.find(id).orElseThrow();var source=parent.result();
            var result=source.overview()!=null && List.of("completed","empty").contains(source.overview().get("status"))
                ?source.overview():agent.generateOverview(source.segments(),source.pageGroups()==null?List.of():source.pageGroups());
            validate(result,source.segments());
            jdbc.update("UPDATE overview_jobs SET status='completed',run_token=NULL,result_json=?,error_code=NULL WHERE transcription_id=? AND status='processing' AND run_token=?",json.writeValueAsString(result),id,token);
        } catch (Exception e) {
            boolean temporary=e instanceof ResourceAccessException || e instanceof RestClientResponseException r && (r.getStatusCode().value()==429 || r.getStatusCode().is5xxServerError());
            String code=e instanceof RestClientResponseException r && r.getStatusCode().value()==424
                && r.getResponseBodyAsString().contains("overview_provider_payment_required")?"overview_provider_payment_required":"overview_failed";
            jdbc.update("UPDATE overview_jobs SET status=CASE WHEN ? AND attempt_count<3 THEN 'queued' ELSE 'failed' END,run_token=NULL,error_code=? WHERE transcription_id=? AND status='processing' AND run_token=?",temporary,code,id,token);
        }
    }

    static void validate(Map<String,Object> result,List<TranscriptionController.TranscriptSegment> segments) {
        if(result==null)throw new IllegalArgumentException("Missing overview");
        if("empty".equals(result.get("status")) && segments.stream().noneMatch(s->!s.text().isBlank()))return;
        if(!"completed".equals(result.get("status")) || !(result.get("headline") instanceof String headline) || headline.isBlank())
            throw new IllegalArgumentException("Incomplete overview");
        var sources=new HashMap<String,TranscriptionController.TranscriptSegment>();segments.forEach(s->sources.put(s.id(),s));
        for(var section:List.of("summary","objectives","keyPoints","pitfalls","highlights")) {
            if(!(result.get(section) instanceof List<?> items) || section.equals("summary")&&items.isEmpty())throw new IllegalArgumentException("Missing section");
            for(var item:items) {
                if(!(item instanceof Map<?,?> row) || !(row.get("text") instanceof String text) || text.isBlank()
                    || !(row.get("citations") instanceof List<?> refs) || refs.isEmpty())throw new IllegalArgumentException("Missing citation");
                for(var ref:refs) {
                    if(!(ref instanceof Map<?,?> citation))throw new IllegalArgumentException("Invalid citation");
                    var source=sources.get(citation.get("sourceId"));
                    if(source==null || !(citation.get("startMs") instanceof Number start) || !(citation.get("endMs") instanceof Number end)
                       || start.doubleValue()!=source.startMs() || end.doubleValue()!=source.endMs()
                       || !source.text().equals(citation.get("quote")))throw new IllegalArgumentException("Ungrounded citation");
                }
            }
        }
    }
    @PreDestroy public void close(){worker.shutdownNow();}
}

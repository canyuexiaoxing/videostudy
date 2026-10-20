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
import org.springframework.dao.DataAccessException;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClientResponseException;
import java.util.*;
import java.util.concurrent.*;

@RestController
@RequestMapping("/api/transcriptions/{id}/chapters")
@CrossOrigin(origins={"http://localhost:5173","http://127.0.0.1:5173"})
public class ChapterController {
    private static final org.slf4j.Logger log=org.slf4j.LoggerFactory.getLogger(ChapterController.class);
    private final JdbcTemplate jdbc;
    private final ObjectMapper json;
    private final TranscriptionJobStore main;
    private final MediaAnalyzer agent;
    private final ThreadPoolExecutor worker=new ThreadPoolExecutor(1,1,0,TimeUnit.MILLISECONDS,new ArrayBlockingQueue<>(4));
    private final Set<String> dispatched=ConcurrentHashMap.newKeySet();
    public record Job(String id,String status,Map<String,Object> result,String error) {}
    public ChapterController(JdbcTemplate jdbc,ObjectMapper json,TranscriptionJobStore main,MediaAnalyzer agent) {
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
        long started=System.nanoTime();
        try { jdbc.update("INSERT INTO chapter_jobs (transcription_id,status) VALUES (?,'queued')",id); }
        catch (DataAccessException error) {
            if(DatabaseDialect.duplicate(error)) {
                log.info("Job request task={} request={} stage=reuse result=existing elapsedMs={}",id,UUID.randomUUID(),TimeUnit.NANOSECONDS.toMillis(System.nanoTime()-started));
            } else if(error instanceof DataIntegrityViolationException) return;
            else throw error;
        }
        dispatch();
    }
    private Job find(String id) {
        return jdbc.query("SELECT status,result_json,error_code FROM chapter_jobs WHERE transcription_id=?",(r,n)->{
            try { return new Job(id,r.getString(1),r.getString(2)==null?null:json.readValue(r.getString(2),new TypeReference<Map<String,Object>>(){}),r.getString(3)); }
            catch (Exception e) { throw new IllegalStateException("Invalid chapter result",e); }
        },id).stream().findFirst().orElse(new Job(id,"not_requested",null,null));
    }
    @Scheduled(fixedDelay=2000) public void dispatch() {
        for (var id:jdbc.query("SELECT transcription_id FROM chapter_jobs WHERE status='queued' AND attempt_count<3",(r,n)->r.getString(1))) {
            if (!dispatched.add(id)) continue;
            try { worker.execute(()->{try{process(id);}finally{dispatched.remove(id);}}); }
            catch (RejectedExecutionException full) { dispatched.remove(id); }
        }
    }
    @EventListener(ApplicationReadyEvent.class) public void recover() {
        jdbc.update("UPDATE chapter_jobs SET status=CASE WHEN attempt_count<3 THEN 'queued' ELSE 'failed' END,run_token=NULL,error_code='chapter_interrupted' WHERE status='processing'");
        dispatch();
    }
    private void process(String id) {
        var token=UUID.randomUUID().toString();
        if (jdbc.update("UPDATE chapter_jobs SET status='processing',run_token=?,attempt_count=attempt_count+1 WHERE transcription_id=? AND status='queued' AND attempt_count<3",token,id)!=1) return;
        try {
            var parent=main.find(id).orElseThrow();var source=parent.result();
            var result=agent.generateChapters(source.segments(),source.pageGroups()==null?List.of():source.pageGroups());
            validate(result,source.segments());
            jdbc.update("UPDATE chapter_jobs SET status='completed',run_token=NULL,result_json=?,error_code=NULL WHERE transcription_id=? AND status='processing' AND run_token=?",json.writeValueAsString(result),id,token);
        } catch (Exception e) {
            boolean temporary=e instanceof ResourceAccessException || e instanceof RestClientResponseException r && (r.getStatusCode().value()==429 || r.getStatusCode().is5xxServerError());
            jdbc.update("UPDATE chapter_jobs SET status=CASE WHEN ? AND attempt_count<3 THEN 'queued' ELSE 'failed' END,run_token=NULL,error_code='chapter_failed' WHERE transcription_id=? AND status='processing' AND run_token=?",temporary,id,token);
        }
    }
    static void validate(Map<String,Object> result,List<TranscriptionController.TranscriptSegment> segments) {
        if (result==null || !(result.get("chapters") instanceof List<?> chapters)) throw new IllegalArgumentException("Missing chapters");
        if (chapters.isEmpty()) {
            if (!"empty".equals(result.get("status")) || segments.stream().anyMatch(s->!s.text().isBlank())) throw new IllegalArgumentException("Missing source chapters");
            return;
        }
        if (!"completed".equals(result.get("status"))) throw new IllegalArgumentException("Incomplete chapters");
        var sources=new HashMap<String,TranscriptionController.TranscriptSegment>();segments.forEach(s->sources.put(s.id(),s));
        var firstSource=segments.stream().filter(s->!s.text().isBlank()).min(Comparator.comparingLong(TranscriptionController.TranscriptSegment::startMs)).orElseThrow();
        long priorEnd=-1;
        for (int i=0;i<chapters.size();i++) {
            if (!(chapters.get(i) instanceof Map<?,?> c) || !(c.get("title") instanceof String title) || title.isBlank()
                || !(c.get("startMs") instanceof Number start) || !(c.get("endMs") instanceof Number end)) throw new IllegalArgumentException("Invalid chapter");
            var source=sources.get(c.get("sourceSegmentId"));
            if (source==null || start.doubleValue()!=start.longValue() || end.doubleValue()!=end.longValue()
                || i==0 && !source.id().equals(firstSource.id())
                || end.longValue()<=start.longValue() || (i==0?start.longValue()!=0:start.longValue()!=priorEnd || start.longValue()!=source.startMs())) throw new IllegalArgumentException("Ungrounded chapter boundary");
            priorEnd=end.longValue();
        }
        if (priorEnd!=segments.stream().mapToLong(TranscriptionController.TranscriptSegment::endMs).max().orElse(0)) throw new IllegalArgumentException("Incorrect final boundary");
    }
    @PreDestroy public void close(){worker.shutdownNow();}
}

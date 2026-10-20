package cn.videostudy.api;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Positive;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestClient;
import org.springframework.http.client.SimpleClientHttpRequestFactory;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

@RestController
@RequestMapping("/api")
@CrossOrigin(origins = {"http://localhost:5173", "http://127.0.0.1:5173", "app://videostudy"})
public class StudyController {
    private final Map<String, Course> courses = new ConcurrentHashMap<>();
    private final Map<String, Job> jobs = new ConcurrentHashMap<>();
    private final RestClient agent;

    @org.springframework.beans.factory.annotation.Autowired
    public StudyController(@Value("${agent.base-url}") String agentBaseUrl,@Value("${FRAMEWISE_RUNTIME_TOKEN:}") String runtimeToken) {
        var requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(3000);
        requestFactory.setReadTimeout(10000);
        var builder=RestClient.builder().baseUrl(agentBaseUrl).requestFactory(requestFactory);
        if(!runtimeToken.isEmpty())builder.defaultHeader(NativeRuntimeFilter.HEADER,runtimeToken);
        this.agent=builder.build();
    }

    public StudyController(String agentBaseUrl){this(agentBaseUrl,"");}

    @GetMapping("/health")
    public Map<String, String> health() { return Map.of("status", "ok"); }

    @PostMapping("/courses")
    public ResponseEntity<Course> createCourse(@Valid @RequestBody CreateCourse request) {
        var course = new Course(UUID.randomUUID().toString(), request.title(), request.sizeBytes());
        courses.put(course.id(), course);
        return ResponseEntity.status(HttpStatus.CREATED).body(course);
    }

    @PostMapping("/courses/{courseId}/jobs")
    public ResponseEntity<?> createJob(@PathVariable String courseId) {
        if (!courses.containsKey(courseId)) return ResponseEntity.status(404).body(Map.of("error", "course_not_found"));
        var job = new Job(UUID.randomUUID().toString(), courseId, "queued", null, null);
        jobs.put(job.id(), job);
        try {
            var result = agent.post().uri("/analyze-demo").body(Map.of("courseId", courseId)).retrieve().body(DemoResult.class);
            jobs.put(job.id(), new Job(job.id(), courseId, "completed", result, null));
        } catch (Exception error) {
            jobs.put(job.id(), new Job(job.id(), courseId, "failed", null, "agent_unavailable"));
        }
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(jobs.get(job.id()));
    }

    @GetMapping("/jobs/{jobId}")
    public ResponseEntity<?> getJob(@PathVariable String jobId) {
        var job = jobs.get(jobId);
        return job == null ? ResponseEntity.status(404).body(Map.of("error", "job_not_found")) : ResponseEntity.ok(job);
    }

    public record CreateCourse(@NotBlank String title, @Positive long sizeBytes) {}
    public record Course(String id, String title, long sizeBytes) {}
    public record DemoResult(String summary, java.util.List<DemoPoint> points) {}
    public record DemoPoint(String id, String title, long startMs, long endMs, String evidence) {}
    public record Job(String id, String courseId, String status, DemoResult result, String error) {}
}

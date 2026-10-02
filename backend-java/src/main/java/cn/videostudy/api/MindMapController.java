package cn.videostudy.api;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/transcriptions")
@CrossOrigin(origins = {"http://localhost:5173", "http://127.0.0.1:5173"})
public class MindMapController {
    private final TranscriptionJobStore store;
    private final MediaAnalyzer analyzer;

    public MindMapController(TranscriptionJobStore store, MediaAnalyzer analyzer) {
        this.store = store;
        this.analyzer = analyzer;
    }

    @PostMapping("/{id}/mind-map")
    public ResponseEntity<?> generate(@PathVariable String id,
                                      @RequestParam(defaultValue = "false") boolean refresh) {
        var found = store.find(id);
        if (found.isEmpty()) return ResponseEntity.status(404).body(Map.of("error", "job_not_found"));
        var job = found.get();
        if (!"completed".equals(job.status()) || job.result() == null)
            return ResponseEntity.status(409).body(Map.of("error", "job_not_completed"));
        var previous = job.result().mindMap();
        if (!refresh && previous != null && "completed".equals(previous.status())) return ResponseEntity.ok(previous);
        try {
            var result = job.result();
            var generated = analyzer.generateMindMap(result.segments() == null ? List.of() : result.segments(),
                result.pageGroups() == null ? List.of() : result.pageGroups());
            if (!MindMapValidator.isGrounded(generated, result.segments()))
                throw new IllegalStateException("Agent returned an ungrounded mind map");
            if (refresh && previous != null && "completed".equals(previous.status()) &&
                !"completed".equals(generated.status()))
                throw new IllegalStateException("Refreshed mind map is incomplete; preserving previous result");
            store.saveMindMap(id, generated);
            return ResponseEntity.ok(generated);
        } catch (Exception error) {
            return ResponseEntity.status(502).body(Map.of("error", "mind_map_generation_failed"));
        }
    }
}

package cn.videostudy.api;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.*;

@RestController
@RequestMapping("/api/transcriptions/{id}/subtitles")
@CrossOrigin(origins = {"http://localhost:5173", "http://127.0.0.1:5173", "app://videostudy"})
public class SubtitleController {
    private final SubtitleService subtitles;
    private final TranscriptionJobStore transcriptions;
    public record Request(String targetLanguage, boolean force) {}
    public SubtitleController(SubtitleService subtitles, TranscriptionJobStore transcriptions) { this.subtitles = subtitles; this.transcriptions = transcriptions; }
    @GetMapping public ResponseEntity<?> get(@PathVariable String id, @RequestParam(defaultValue = "source") String targetLanguage) {
        var invalid = invalid(id, targetLanguage); if (invalid != null) return invalid;
        return ResponseEntity.ok(subtitles.get(id, targetLanguage));
    }
    @PostMapping public ResponseEntity<?> generate(@PathVariable String id, @RequestBody(required = false) Request body) {
        String target = body == null || body.targetLanguage() == null ? "source" : body.targetLanguage();
        var invalid = invalid(id, target); if (invalid != null) return invalid;
        var job = body != null && body.force() ? subtitles.request(id, target, true) : subtitles.request(id, target);
        return ResponseEntity.status(List.of("awaiting_source", "queued", "processing").contains(job.status()) ? 202 : 200).body(job);
    }
    private ResponseEntity<?> invalid(String id, String target) {
        if (!validId(id)) return ResponseEntity.badRequest().body(Map.of("error", "invalid_job_id"));
        if (!List.of("source", "zh", "en").contains(target)) return ResponseEntity.badRequest().body(Map.of("error", "invalid_subtitle_target_language"));
        if (transcriptions.find(id).isEmpty()) return ResponseEntity.status(404).body(Map.of("error", "job_not_found"));
        return null;
    }
    static boolean validId(String id) { try { return UUID.fromString(id).toString().equalsIgnoreCase(id); } catch (IllegalArgumentException e) { return false; } }
}

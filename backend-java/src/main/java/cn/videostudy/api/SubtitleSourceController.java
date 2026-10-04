package cn.videostudy.api;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.Map;

/** Internal callback intentionally has no cross-origin allowance. Tokens never enter client payloads. */
@RestController
@RequestMapping("/api/internal/transcriptions")
public class SubtitleSourceController {
    private final SubtitleService subtitles;
    public SubtitleSourceController(SubtitleService subtitles) { this.subtitles = subtitles; }
    @PostMapping("/{id}/subtitle-source")
    public ResponseEntity<?> capture(@PathVariable String id, @RequestHeader(value = "X-Subtitle-Token", required = false) String token,
                                     @RequestBody SubtitleJobStore.Source source) {
        if (!SubtitleController.validId(id)) return ResponseEntity.badRequest().body(Map.of("error", "invalid_job_id"));
        try {
            if (!subtitles.acceptSource(id, token, source)) return ResponseEntity.status(403).body(Map.of("error", "subtitle_callback_denied"));
            return ResponseEntity.accepted().body(Map.of("status", "source_received"));
        } catch (IllegalArgumentException invalid) { return ResponseEntity.badRequest().body(Map.of("error", "invalid_subtitle_source")); }
    }
}

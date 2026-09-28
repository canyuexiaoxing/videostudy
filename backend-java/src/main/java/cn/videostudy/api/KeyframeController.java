package cn.videostudy.api;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.UUID;

@RestController
@RequestMapping("/api/transcriptions")
@CrossOrigin(origins = {"http://localhost:5173", "http://127.0.0.1:5173", "app://videostudy"})
public class KeyframeController {
    private final Path keyframeRoot;
    private final TranscriptionJobStore store;

    public KeyframeController(@Value("${keyframe.dir}") String keyframeDir, TranscriptionJobStore store) {
        this.keyframeRoot = Path.of(keyframeDir).toAbsolutePath().normalize();
        this.store = store;
    }

    @GetMapping(value = "/{id}/frames/{timeMs}", produces = MediaType.IMAGE_JPEG_VALUE)
    public ResponseEntity<byte[]> frame(@PathVariable String id, @PathVariable long timeMs) throws IOException {
        try { UUID.fromString(id); }
        catch (IllegalArgumentException error) { return ResponseEntity.notFound().build(); }
        if (timeMs < 0) return ResponseEntity.notFound().build();
        var job = store.find(id);
        if (job.isEmpty() || !"completed".equals(job.get().status()) || job.get().result() == null) {
            return ResponseEntity.notFound().build();
        }
        var result = job.get().result();
        boolean legacyImage = result.visualEvidence() != null && result.visualEvidence().stream().anyMatch(
            item -> item.frameTimeMs() == timeMs && item.imageAnalysis() != null);
        boolean groupedImage = result.pageGroups() != null && result.pageGroups().stream().anyMatch(
            page -> page.memberFrameTimesMs() != null && page.memberFrameTimesMs().contains(timeMs) &&
                result.visualEvidence() != null && result.visualEvidence().stream().anyMatch(
                    item -> item.frameTimeMs() == timeMs));
        if (!legacyImage && !groupedImage) return ResponseEntity.notFound().build();
        var path = keyframeRoot.resolve(id).resolve(timeMs + ".jpg");
        if (!Files.isRegularFile(path)) return ResponseEntity.notFound().build();
        return ResponseEntity.ok().contentType(MediaType.IMAGE_JPEG).body(Files.readAllBytes(path));
    }
}

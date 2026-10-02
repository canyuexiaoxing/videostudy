package cn.videostudy.api;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.io.IOException;
import java.nio.file.FileVisitResult;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.SimpleFileVisitor;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/transcriptions")
@CrossOrigin(origins = {"http://localhost:5173", "http://127.0.0.1:5173", "app://videostudy"})
public class TranscriptionDeletionController {
    private final Path uploadRoot;
    private final Path keyframeRoot;
    private final TranscriptionJobStore store;

    public TranscriptionDeletionController(@Value("${media.temp-dir}") String tempDir,
                                           @Value("${keyframe.dir}") String keyframeDir,
                                           TranscriptionJobStore store) {
        this.uploadRoot = Path.of(tempDir).toAbsolutePath().normalize();
        this.keyframeRoot = Path.of(keyframeDir).toAbsolutePath().normalize();
        this.store = store;
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<?> delete(@PathVariable String id) throws IOException {
        if (!validJobId(id)) return ResponseEntity.badRequest().body(Map.of("error", "invalid_job_id"));
        var job = store.find(id);
        if (job.isEmpty()) return ResponseEntity.notFound().build();
        if ("queued".equals(job.get().status()) || "processing".equals(job.get().status())) {
            return ResponseEntity.status(409).body(Map.of("error", "analysis_in_progress"));
        }

        Files.deleteIfExists(uploadRoot.resolve(id));
        deleteKeyframes(keyframeRoot.resolve(id));
        store.delete(id);
        return ResponseEntity.noContent().build();
    }

    private static boolean validJobId(String id) {
        try { return UUID.fromString(id).toString().equalsIgnoreCase(id); }
        catch (IllegalArgumentException error) { return false; }
    }

    private void deleteKeyframes(Path target) throws IOException {
        target = target.toAbsolutePath().normalize();
        if (!target.startsWith(keyframeRoot) || target.equals(keyframeRoot))
            throw new IllegalArgumentException("Keyframe path is outside the configured root");
        if (!Files.exists(target)) return;
        Files.walkFileTree(target, new SimpleFileVisitor<>() {
            @Override public FileVisitResult visitFile(Path file, BasicFileAttributes attributes) throws IOException {
                Files.delete(file);
                return FileVisitResult.CONTINUE;
            }
            @Override public FileVisitResult postVisitDirectory(Path directory, IOException error) throws IOException {
                if (error != null) throw error;
                Files.delete(directory);
                return FileVisitResult.CONTINUE;
            }
        });
    }
}

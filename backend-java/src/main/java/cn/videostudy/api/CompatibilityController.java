package cn.videostudy.api;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.multipart.MultipartFile;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/compatibility")
@CrossOrigin(origins={"http://localhost:5173", "http://127.0.0.1:5173", "app://videostudy"})
public class CompatibilityController {
    private final Path root;
    private final RestClient agent;
    public CompatibilityController(@Value("${media.temp-dir}") String directory,
                                   @Value("${agent.base-url}") String url) {
        root = Path.of(directory).toAbsolutePath().normalize().resolve("compatibility");
        var factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(3000); factory.setReadTimeout(30000);
        agent = RestClient.builder().baseUrl(url).requestFactory(factory).build();
    }
    private Path path(String id) {
        if (!UUID.fromString(id).toString().equals(id)) throw new IllegalArgumentException("invalid_job_id");
        return root.resolve(id);
    }
    @GetMapping("/capabilities") public Map<?,?> capabilities() {
        return agent.get().uri("/compatibility/capabilities").retrieve().body(Map.class);
    }
    @PostMapping public ResponseEntity<?> upload(@RequestParam("file") MultipartFile file) throws IOException {
        if (file.isEmpty()) return ResponseEntity.badRequest().body(Map.of("error", "empty_file"));
        String id = UUID.randomUUID().toString();
        Path directory = path(id);
        Files.createDirectories(directory);
        try {
            file.transferTo(directory.resolve("input"));
            var state = agent.post().uri("/compatibility").body(Map.of("id", id)).retrieve().body(Map.class);
            return ResponseEntity.accepted().body(state);
        } catch (RuntimeException | IOException error) {
            Files.deleteIfExists(directory.resolve("input"));
            try { Files.deleteIfExists(directory); } catch (IOException ignored) { /* Agent may already own an active job. */ }
            throw error;
        }
    }
    @ExceptionHandler(RestClientResponseException.class)
    public ResponseEntity<?> agentError(RestClientResponseException error) {
        return ResponseEntity.status(error.getStatusCode()).body(Map.of("error", "gpu_conversion_service_error"));
    }
    @GetMapping("/{id}") public ResponseEntity<?> status(@PathVariable String id) {
        try { path(id); } catch (IllegalArgumentException error) { return ResponseEntity.badRequest().build(); }
        try { return ResponseEntity.ok(agent.get().uri("/compatibility/{id}", id).retrieve().body(Map.class)); }
        catch (RestClientResponseException error) { return ResponseEntity.status(error.getStatusCode()).build(); }
    }
    @GetMapping(value="/{id}/video", produces="video/mp4") public ResponseEntity<?> video(@PathVariable String id) {
        Path output;
        try { output = path(id).resolve("playback.mp4"); } catch (IllegalArgumentException error) { return ResponseEntity.badRequest().build(); }
        var state = status(id);
        if (!(state.getBody() instanceof Map<?,?> body) || !"completed".equals(body.get("status")) || !Files.isRegularFile(output))
            return ResponseEntity.notFound().build();
        return ResponseEntity.ok().contentType(MediaType.valueOf("video/mp4"))
            .header("Cache-Control", "no-store").body(new FileSystemResource(output));
    }
    @DeleteMapping("/{id}") public ResponseEntity<?> delete(@PathVariable String id) {
        try { path(id); } catch (IllegalArgumentException error) { return ResponseEntity.badRequest().build(); }
        agent.delete().uri("/compatibility/{id}", id).retrieve().toBodilessEntity();
        return ResponseEntity.noContent().build();
    }
}

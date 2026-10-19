package cn.videostudy.api;
import org.springframework.context.annotation.Profile;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import java.util.Map;
@RestController
@Profile("sqlite")
@RequestMapping("/api/sync")
public class LocalSyncController {
 private final LocalSyncService service;
 public LocalSyncController(LocalSyncService service){this.service=service;}
 @GetMapping("/status") public Map<String,Object> status(){return service.status();}
 @PostMapping("/connection") public Map<String,Object> connection(){return service.connect();}
 @PostMapping("/courses/{id}/push") public Map<String,Object> push(@PathVariable String id){return service.push(id);}
 @PostMapping("/courses/{id}/pull") public Map<String,Object> pull(@PathVariable String id){return service.pull(id);}
 @ExceptionHandler(IllegalArgumentException.class) public ResponseEntity<?> invalid(IllegalArgumentException e){String code=e.getMessage();return ResponseEntity.status(java.util.Set.of("local_changes","sync_conflict","course_busy").contains(code)?409:java.util.Set.of("sync_unavailable","sync_server_error").contains(code)?503:code.equals("course_not_found")?404:400).body(Map.of("error",code));}
}

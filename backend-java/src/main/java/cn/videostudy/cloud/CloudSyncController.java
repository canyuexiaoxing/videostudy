package cn.videostudy.cloud;
import cn.videostudy.api.CourseSnapshotStore;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.HttpStatus;
import java.security.MessageDigest;
import java.nio.charset.StandardCharsets;
import java.util.*;
@RestController
@RequestMapping("/api/cloud-sync")
public class CloudSyncController {
 private static final org.slf4j.Logger log=org.slf4j.LoggerFactory.getLogger(CloudSyncController.class);
 private final CloudDocumentStore store;private final String token,owner;
 public record Upload(long expectedRevision,CourseSnapshotStore.Snapshot snapshot){}
 public CloudSyncController(CloudDocumentStore store,@Value("${SYNC_TOKEN:}") String token,@Value("${SYNC_OWNER:private}") String owner){this.store=store;this.token=token;this.owner=owner;}
 private void authorize(String supplied){if(token.length()<32||supplied==null||!MessageDigest.isEqual(token.getBytes(StandardCharsets.UTF_8),supplied.getBytes(StandardCharsets.UTF_8)))throw new ResponseStatusException(HttpStatus.UNAUTHORIZED,"sync_unauthorized");}
 @GetMapping("/health") public Map<String,Object> health(@RequestHeader(value="X-Framewise-Sync",required=false) String supplied){authorize(supplied);store.list(owner);return Map.of("status","ok","storage","mysql");}
 @GetMapping("/documents") public List<CloudDocumentStore.Summary> list(@RequestHeader(value="X-Framewise-Sync",required=false) String supplied){authorize(supplied);return store.list(owner);}
 @GetMapping("/documents/{id}") public CloudDocumentStore.Document get(@PathVariable String id,@RequestHeader(value="X-Framewise-Sync",required=false) String supplied){authorize(supplied);return store.get(owner,id);}
 @PutMapping("/documents/{id}") public CloudDocumentStore.Document put(@PathVariable String id,@RequestHeader(value="X-Framewise-Sync",required=false) String supplied,@RequestBody Upload upload){authorize(supplied);long start=System.nanoTime();try{var result=store.put(owner,id,upload.expectedRevision(),upload.snapshot());log.info("Cloud sync task={} request={} stage=store result=completed revision={} elapsed_ms={}",id,UUID.randomUUID(),result.revision(),(System.nanoTime()-start)/1000000);return result;}catch(RuntimeException e){log.warn("Cloud sync task={} stage=store result=failed type={} elapsed_ms={}",id,e.getClass().getSimpleName(),(System.nanoTime()-start)/1000000);throw e;}}
 @ExceptionHandler(IllegalArgumentException.class) public org.springframework.http.ResponseEntity<?> invalid(IllegalArgumentException e){var safe=Set.of("sync_conflict","invalid_snapshot","invalid_course_id","course_busy","course_not_found","snapshot_too_large");String reason=safe.contains(e.getMessage())?e.getMessage():"invalid_snapshot";return org.springframework.http.ResponseEntity.status(reason.equals("sync_conflict")||reason.equals("course_busy")?409:reason.equals("course_not_found")?404:400).body(Map.of("error",reason));}
}

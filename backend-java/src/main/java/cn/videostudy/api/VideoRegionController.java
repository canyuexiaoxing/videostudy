package cn.videostudy.api;
import org.springframework.web.bind.annotation.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.core.ParameterizedTypeReference;
import java.util.*;
import java.util.concurrent.Semaphore;
@RestController
@RequestMapping("/api/video-region-detections")
@CrossOrigin(origins={"http://localhost:5173","http://127.0.0.1:5173"})
public class VideoRegionController {
    private final RestClient agent;
    private final Semaphore slots=new Semaphore(2);
    public record Frame(long timeMs,String image){}
    public record Batch(List<Frame> frames){}
    @org.springframework.beans.factory.annotation.Autowired
    public VideoRegionController(@Value("${agent.base-url}")String base){
        var factory=new SimpleClientHttpRequestFactory();factory.setConnectTimeout(3000);factory.setReadTimeout(60000);
        agent=RestClient.builder().baseUrl(base).requestFactory(factory).build();
    }
    VideoRegionController(RestClient client){agent=client;}
    @PostMapping public ResponseEntity<?> detect(@RequestBody Batch request){
        if(request.frames()==null||request.frames().isEmpty()||request.frames().size()>4)return ResponseEntity.badRequest().body(Map.of("error","invalid_region_frames"));
        var seen=new HashSet<Long>();
        for(var f:request.frames())if(f==null||f.timeMs()<0||f.timeMs()>9007199254740991L||!seen.add(f.timeMs())||f.image()==null||f.image().length()>1500000||!f.image().startsWith("data:image/jpeg;base64,"))return ResponseEntity.badRequest().body(Map.of("error","invalid_region_frames"));
        if(!slots.tryAcquire())return ResponseEntity.status(429).body(Map.of("error","region_detector_busy"));
        try{
            var result=agent.post().uri("/video-region-detections").body(request).retrieve().body(new ParameterizedTypeReference<Map<String,Object>>(){});
            if(result==null)throw new IllegalStateException();
            return ResponseEntity.ok(result);
        }catch(RestClientResponseException e){return ResponseEntity.status(e.getStatusCode().value()).body(Map.of("error","region_detector_failed"));}
        catch(Exception e){return ResponseEntity.status(503).body(Map.of("error","region_detector_unavailable"));}
        finally{slots.release();}
    }
}

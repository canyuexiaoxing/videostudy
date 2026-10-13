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
    @org.springframework.beans.factory.annotation.Autowired(required=false)
    private OverviewController overviews;

    public MindMapController(TranscriptionJobStore store, MediaAnalyzer analyzer) {
        this.store = store;
        this.analyzer = analyzer;
    }

    public ResponseEntity<?> generate(String id, boolean refresh) { return generate(id, refresh, false); }

    public ResponseEntity<?> generate(String id, boolean refresh, boolean groupedAnalysis) { return generate(id,refresh,groupedAnalysis,null); }

    @PostMapping("/{id}/mind-map")
    public ResponseEntity<?> generate(@PathVariable String id,
                                      @RequestParam(defaultValue = "false") boolean refresh,
                                      @RequestParam(defaultValue = "false") boolean groupedAnalysis,
                                      @RequestParam(required = false) String mindMapMode) {
        if (mindMapMode!=null&&!List.of("legacy","grouped","direct").contains(mindMapMode))
            return ResponseEntity.badRequest().body(Map.of("error","invalid_mind_map_mode"));
        var found = store.find(id);
        if (found.isEmpty()) return ResponseEntity.status(404).body(Map.of("error", "job_not_found"));
        var job = found.get();
        if (!"completed".equals(job.status()) || job.result() == null)
            return ResponseEntity.status(409).body(Map.of("error", "job_not_completed"));
        var previous = job.result().mindMap();
        if (!refresh && previous != null && "completed".equals(previous.status())) return ResponseEntity.ok(previous);
        try {
            var result = job.result();
            var segments = result.segments() == null ? List.<TranscriptionController.TranscriptSegment>of() : result.segments();
            var pages = result.pageGroups() == null ? List.<TranscriptionController.PageGroup>of() : result.pageGroups();
            String selected=mindMapMode!=null?mindMapMode:groupedAnalysis?"grouped":store.findMindMapMode(id);
            if(selected==null) selected=store.findGroupedAnalysis(id)?"grouped":"legacy";
            var visuals=result.visualEvidence()==null?List.<TranscriptionController.VisualEvidence>of():result.visualEvidence();
            var generated = "direct".equals(selected) ? analyzer.generateMindMap(id,false,segments,pages,visuals,store.findIgnoredRegion(id),"direct")
                : "grouped".equals(selected) ? analyzer.generateMindMap(id,true,segments,pages,visuals,store.findIgnoredRegion(id)) : analyzer.generateMindMap(segments,pages);
            if (!MindMapValidator.isGrounded(generated, result.segments(), result.visualEvidence()))
                throw new IllegalStateException("Agent returned an ungrounded mind map");
            if (refresh && previous != null && "completed".equals(previous.status()) &&
                !"completed".equals(generated.status()) &&
                !("empty".equals(generated.status()) && generated.examples() != null && !generated.examples().isEmpty()))
                throw new IllegalStateException("Refreshed mind map is incomplete; preserving previous result");
            store.saveMindMap(id, generated);
            if(overviews!=null && "completed".equals(generated.status())) {
                try {overviews.request(id);}catch(RuntimeException ignored){/* Map is already saved and usable. */}
            }
            return ResponseEntity.ok(generated);
        } catch (Exception error) {
            return ResponseEntity.status(502).body(Map.of("error", "mind_map_generation_failed"));
        }
    }
}

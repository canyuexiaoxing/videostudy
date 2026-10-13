package cn.videostudy.api;

import java.util.HashMap;
import java.util.ArrayDeque;
import java.util.List;
import java.util.Map;

final class MindMapValidator {
    private MindMapValidator() {}

    static boolean isGrounded(TranscriptionController.MindMapResult map,
                              List<TranscriptionController.TranscriptSegment> segments) {
        return isGrounded(map, segments, List.of());
    }

    static boolean isGrounded(TranscriptionController.MindMapResult map,
                              List<TranscriptionController.TranscriptSegment> segments,
                              List<TranscriptionController.VisualEvidence> visuals) {
        var frames = new java.util.HashSet<Long>();
        if (visuals != null) for (var frame : visuals) if (frame != null) frames.add(frame.frameTimeMs());
        if (map == null || map.root() == null || segments == null || map.status() == null ||
            !List.of("completed", "empty", "failed").contains(map.status())) return false;
        var known = new HashMap<String, TranscriptionController.TranscriptSegment>();
        for (var item : segments) known.put(item.id(), item);
        if (!validTree(map.root(), known, frames)) return false;
        if (map.examples() != null) {
            if (map.examples().size() > 4096) return false;
            for (var example : map.examples()) {
                if (example == null || !validTree(example, known, frames) || example.evidenceRefs().isEmpty() || !example.children().isEmpty()) return false;
                if (example.endMs() != example.evidenceRefs().stream().mapToLong(TranscriptionController.MindMapEvidence::endMs).max().orElse(0)) return false;
            }
        }
        if ("completed".equals(map.status()) && map.root().children().isEmpty()) return false;
        return !"empty".equals(map.status()) || map.root().children().isEmpty();
    }

    private static boolean validTree(TranscriptionController.MindMapNode root,
                                     Map<String, TranscriptionController.TranscriptSegment> known, java.util.Set<Long> frames) {
        var pending = new ArrayDeque<TranscriptionController.MindMapNode>();
        pending.push(root);
        var count = 0;
        while (!pending.isEmpty()) {
            var node = pending.pop();
            if (++count > 4096 || node.id() == null || node.title() == null || node.title().isBlank() ||
                node.children() == null || node.evidenceRefs() == null ||
                node.startMs() < 0 || node.endMs() < node.startMs()) return false;
            for (var ref : node.evidenceRefs()) {
                if (ref == null) return false;
                if ("image".equals(ref.sourceType())) {
                    if (!frames.contains(ref.startMs()) || ref.startMs() != ref.endMs() ||
                        !("frame_" + ref.startMs()).equals(ref.sourceId()) || !"课件截图".equals(ref.quote())) return false;
                } else if ("transcript".equals(ref.sourceType())) {
                    var source = known.get(ref.sourceId());
                    if (source == null || source.startMs() != ref.startMs() ||
                        source.endMs() != ref.endMs() || !source.text().equals(ref.quote())) return false;
                } else return false;
            }
            if (!node.evidenceRefs().isEmpty() && (node.startMs() != node.evidenceRefs().stream().mapToLong(TranscriptionController.MindMapEvidence::startMs).min().orElse(0)
                || node.endMs() != node.evidenceRefs().stream().mapToLong(TranscriptionController.MindMapEvidence::endMs).max().orElse(0))) return false;
            if (node.children().isEmpty() && (node.details() == null || node.details().isEmpty()) && node != root && node.evidenceRefs().isEmpty()) return false;
            if (node.details() != null) for (var detail : node.details()) {
                if (detail == null) return false;
                pending.push(detail);
            }
            for (var child : node.children()) {
                if (child == null) return false;
                pending.push(child);
            }
        }
        return true;
    }
}

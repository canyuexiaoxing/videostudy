package cn.videostudy.api;

import java.util.HashMap;
import java.util.ArrayDeque;
import java.util.List;
import java.util.Map;

final class MindMapValidator {
    private MindMapValidator() {}

    static boolean isGrounded(TranscriptionController.MindMapResult map,
                              List<TranscriptionController.TranscriptSegment> segments) {
        if (map == null || map.root() == null || segments == null || map.status() == null ||
            !List.of("completed", "empty", "failed").contains(map.status())) return false;
        var known = new HashMap<String, TranscriptionController.TranscriptSegment>();
        for (var item : segments) known.put(item.id(), item);
        if (!validTree(map.root(), known)) return false;
        if ("completed".equals(map.status()) && map.root().children().isEmpty()) return false;
        return !"empty".equals(map.status()) || map.root().children().isEmpty();
    }

    private static boolean validTree(TranscriptionController.MindMapNode root,
                                     Map<String, TranscriptionController.TranscriptSegment> known) {
        var pending = new ArrayDeque<TranscriptionController.MindMapNode>();
        pending.push(root);
        var count = 0;
        while (!pending.isEmpty()) {
            var node = pending.pop();
            if (++count > 4096 || node.id() == null || node.title() == null || node.title().isBlank() ||
                node.children() == null || node.evidenceRefs() == null ||
                node.startMs() < 0 || node.endMs() < node.startMs()) return false;
            for (var ref : node.evidenceRefs()) {
                if (ref == null || !"transcript".equals(ref.sourceType())) return false;
                var source = known.get(ref.sourceId());
                if (source == null || source.startMs() != ref.startMs() ||
                    source.endMs() != ref.endMs() || !source.text().equals(ref.quote())) return false;
            }
            if (!node.evidenceRefs().isEmpty() && node.startMs() != node.evidenceRefs().get(0).startMs())
                return false;
            if (node.children().isEmpty() && node != root && node.evidenceRefs().isEmpty()) return false;
            for (var child : node.children()) {
                if (child == null) return false;
                pending.push(child);
            }
        }
        return true;
    }
}

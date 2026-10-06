package cn.videostudy.api;

import java.util.*;

/** Defense in depth: the Python policy remains responsible for linguistic corrections. */
public final class SubtitleResultValidator {
    public static final String PROMPT_VERSION = "subtitle-calibration-v8-page-understanding";
    private SubtitleResultValidator() {}
    public static void validate(SubtitleJobStore.Source source, String requestedTarget, Map<String,Object> result) {
        if (result == null) throw new IllegalArgumentException("No subtitle result");
        String status = string(result.get("status"));
        if (!List.of("completed", "partial", "unsupported", "failed").contains(status)) throw new IllegalArgumentException("Invalid subtitle status");
        if (status.equals("failed") || status.equals("unsupported")) return;
        String language = language(source.language());
        String target = requestedTarget.equals("source") ? language : requestedTarget;
        String mode = target.equals(language) ? "correction" : "translation";
        if (!language.equals(result.get("sourceLanguage")) || !target.equals(result.get("targetLanguage")) || !mode.equals(result.get("mode")))
            throw new IllegalArgumentException("Subtitle language or mode changed");
        var output = list(result.get("segments"));
        if (output.size() != source.segments().size()) throw new IllegalArgumentException("Subtitle segment count changed");
        var changes = new HashMap<String,Map<?,?>>();
        for (var value : list(result.get("changes"))) {
            var change = map(value);
            var segmentId = string(change.get("segmentId"));
            if (changes.put(segmentId, change) != null) throw new IllegalArgumentException("Duplicate subtitle change");
        }
        var changed = new HashSet<String>();
        for (int i = 0; i < output.size(); i++) {
            var original = source.segments().get(i); var segment = map(output.get(i));
            if (!original.id().equals(segment.get("id")) || !sameTime(segment.get("startMs"), original.startMs()) || !sameTime(segment.get("endMs"), original.endMs()))
                throw new IllegalArgumentException("Subtitle segment identity or timing changed");
            var text = string(segment.get("text"));
            if (text.isBlank() && !original.text().isBlank()) throw new IllegalArgumentException("Empty subtitle replacement");
            if (!text.equals(original.text())) {
                changed.add(original.id()); var change = changes.get(original.id());
                if (change == null || !original.text().equals(change.get("originalText")) || !text.equals(change.get("text")) || string(change.get("reason")).isBlank())
                    throw new IllegalArgumentException("Untracked subtitle change");
                for (var evidenceValue : list(change.get("evidence"))) {
                    var evidence = map(evidenceValue); var evidenceText = string(evidence.get("text"));
                    if (!(evidence.get("sourceFrameTimeMs") instanceof Number time) || !hasEvidence(source, original, time.longValue(), evidenceText))
                        throw new IllegalArgumentException("Subtitle correction references unavailable OCR evidence");
                }
            }
        }
        if (!changes.keySet().equals(changed)) throw new IllegalArgumentException("Subtitle change records do not match segments");
    }
    private static boolean hasEvidence(SubtitleJobStore.Source source, TranscriptionController.TranscriptSegment segment, long time, String text) {
        if (source.pageGroups() == null) return false;
        var pages = source.pageGroups().stream().filter(page -> page.ocrLines() != null).toList();
        var relevant = pages.stream().filter(page -> gap(page, segment) <= 30000).toList();
        return relevant.stream()
            .flatMap(page -> page.ocrLines().stream()).anyMatch(line -> line.sourceFrameTimeMs() == time && Objects.equals(line.text(), text));
    }
    private static long gap(TranscriptionController.PageGroup page, TranscriptionController.TranscriptSegment segment) {
        return Math.max(0, Math.max(page.firstFrameTimeMs() - segment.endMs(), segment.startMs() - page.lastFrameTimeMs()));
    }
    private static boolean sameTime(Object value, long expected) { return value instanceof Number number && number.doubleValue() == expected; }
    private static String string(Object value) { if (!(value instanceof String text)) throw new IllegalArgumentException("Missing subtitle field"); return text; }
    private static List<?> list(Object value) { if (!(value instanceof List<?> list)) throw new IllegalArgumentException("Missing subtitle list"); return list; }
    private static Map<?,?> map(Object value) { if (!(value instanceof Map<?,?> map)) throw new IllegalArgumentException("Invalid subtitle object"); return map; }
    private static String language(String value) { return value.toLowerCase(Locale.ROOT).replace('_', '-').split("-")[0]; }
}

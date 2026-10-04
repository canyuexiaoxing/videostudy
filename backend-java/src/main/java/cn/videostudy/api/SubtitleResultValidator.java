package cn.videostudy.api;

import java.util.*;
import java.util.regex.Pattern;

/** Defense in depth: the Python policy remains responsible for linguistic corrections. */
public final class SubtitleResultValidator {
    private static final Pattern NUMBERS = Pattern.compile("\\d+(?:[.,]\\d+)*[%％]?|[=<>≤≥×÷+*/^]");
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
                if (mode.equals("correction")) {
                    int limit = Math.max(2, (int)Math.floor(Math.max(1, original.text().length()) * 0.4));
                    if (distance(original.text(), text) > limit || !numericTokens(original.text()).equals(numericTokens(text)))
                        throw new IllegalArgumentException("Correction changes too much text or numeric evidence");
                }
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
        return source.pageGroups().stream().filter(page -> page.ocrLines() != null &&
            segment.endMs() + 2000 >= page.firstFrameTimeMs() && segment.startMs() - 2000 <= page.lastFrameTimeMs())
            .flatMap(page -> page.ocrLines().stream()).anyMatch(line -> line.sourceFrameTimeMs() == time && Objects.equals(line.text(), text));
    }
    private static boolean sameTime(Object value, long expected) { return value instanceof Number number && number.doubleValue() == expected; }
    private static String string(Object value) { if (!(value instanceof String text)) throw new IllegalArgumentException("Missing subtitle field"); return text; }
    private static List<?> list(Object value) { if (!(value instanceof List<?> list)) throw new IllegalArgumentException("Missing subtitle list"); return list; }
    private static Map<?,?> map(Object value) { if (!(value instanceof Map<?,?> map)) throw new IllegalArgumentException("Invalid subtitle object"); return map; }
    private static String language(String value) { return value.toLowerCase(Locale.ROOT).replace('_', '-').split("-")[0]; }
    private static List<String> numericTokens(String value) { return NUMBERS.matcher(value).results().map(match -> match.group()).toList(); }
    private static int distance(String left, String right) {
        var prior = new int[right.length()+1]; for (int j = 0; j <= right.length(); j++) prior[j] = j;
        for (int i = 1; i <= left.length(); i++) {
            var current = new int[right.length()+1]; current[0] = i;
            for (int j = 1; j <= right.length(); j++) current[j] = Math.min(Math.min(prior[j]+1, current[j-1]+1), prior[j-1] + (left.charAt(i-1)==right.charAt(j-1) ? 0 : 1));
            prior = current;
        }
        return prior[right.length()];
    }
}

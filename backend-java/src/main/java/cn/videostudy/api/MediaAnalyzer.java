package cn.videostudy.api;

import java.util.List;
import java.util.Map;

@FunctionalInterface
public interface MediaAnalyzer {
    default Map<String,Object> chatQuestion(Map<String,Object> source) { throw new UnsupportedOperationException("Chat unavailable"); }
    default Map<String,Object> generatePractice(Map<String,Object> source) { throw new UnsupportedOperationException("Practice unavailable"); }
    default Map<String,Object> generateOverview(List<TranscriptionController.TranscriptSegment> segments,
        List<TranscriptionController.PageGroup> pages) { throw new UnsupportedOperationException("Overview unavailable"); }
    default Map<String,Object> generateOverview(String courseId,TranscriptionController.TranscriptResult source) {
        return generateOverview(source);
    }
    default Map<String,Object> generateOverview(TranscriptionController.TranscriptResult source) {
        return generateOverview(source.segments(),source.pageGroups()==null?List.of():source.pageGroups());
    }
    default Map<String,Object> generateChapters(List<TranscriptionController.TranscriptSegment> segments,
        List<TranscriptionController.PageGroup> pages) { throw new UnsupportedOperationException("Chapters unavailable"); }
    TranscriptionController.TranscriptResult analyze(String fileId, String mode);

    default TranscriptionController.TranscriptResult analyze(String fileId, String mode, String visualAnalysisMode) {
        return analyze(fileId, mode);
    }

    default TranscriptionController.TranscriptResult analyze(String fileId, String mode,
                                                              String visualAnalysisMode, double coarseChangePercent) {
        return analyze(fileId, mode, visualAnalysisMode);
    }

    default TranscriptionController.TranscriptResult analyze(String fileId, String mode, String visualAnalysisMode,
                                                              double coarseChangePercent, String subtitleCallbackToken) {
        return analyze(fileId, mode, visualAnalysisMode, coarseChangePercent);
    }

    default TranscriptionController.TranscriptResult analyze(String fileId, String mode, String visualAnalysisMode,
            double coarseChangePercent, int coarseSampleSeconds, String subtitleCallbackToken) {
        return subtitleCallbackToken == null ? analyze(fileId, mode, visualAnalysisMode, coarseChangePercent)
            : analyze(fileId, mode, visualAnalysisMode, coarseChangePercent, subtitleCallbackToken);
    }

    default TranscriptionController.TranscriptResult analyze(String fileId, String mode, String visualMode,
            double threshold, int sampleSeconds, String callbackToken, IgnoreRegion region) {
        if (region != null) throw new UnsupportedOperationException("Ignored regions are unavailable");
        return analyze(fileId, mode, visualMode, threshold, sampleSeconds, callbackToken);
    }

    default TranscriptionController.TranscriptResult analyze(String fileId, String mode, String visualMode,
            double threshold, int seconds, String token, IgnoreRegion region, boolean groupedAnalysis) {
        return analyze(fileId, mode, visualMode, threshold, seconds, token, region);
    }
    default TranscriptionController.TranscriptResult analyze(String fileId, String mode, String visualMode,
            double threshold, int seconds, String token, IgnoreRegion region, boolean groupedAnalysis, String mindMapMode) {
        if ("direct".equals(mindMapMode)) throw new UnsupportedOperationException("Direct mind map unavailable");
        return analyze(fileId, mode, visualMode, threshold, seconds, token, region, "grouped".equals(mindMapMode));
    }
    default TranscriptionController.MindMapResult generateMindMap(String courseId, boolean groupedAnalysis,
            List<TranscriptionController.TranscriptSegment> segments, List<TranscriptionController.PageGroup> pages,
            List<TranscriptionController.VisualEvidence> visuals, IgnoreRegion region, String mindMapMode) {
        if ("direct".equals(mindMapMode)) throw new UnsupportedOperationException("Direct mind map unavailable");
        return "grouped".equals(mindMapMode) ? generateMindMap(courseId,true,segments,pages,visuals,region) : generateMindMap(segments,pages);
    }
    default void cancelAnalysis(String fileId) {}
    default void resetAnalysis(String fileId) {}
    default TranscriptionController.MindMapResult generateMindMap(String courseId, boolean groupedAnalysis,
            List<TranscriptionController.TranscriptSegment> segments, List<TranscriptionController.PageGroup> pages) {
        return generateMindMap(segments, pages);
    }

    default TranscriptionController.MindMapResult generateMindMap(String courseId, boolean groupedAnalysis,
            List<TranscriptionController.TranscriptSegment> segments, List<TranscriptionController.PageGroup> pages,
            List<TranscriptionController.VisualEvidence> visuals) {
        return generateMindMap(courseId, groupedAnalysis, segments, pages);
    }

    default TranscriptionController.MindMapResult generateMindMap(String courseId, boolean groupedAnalysis,
            List<TranscriptionController.TranscriptSegment> segments, List<TranscriptionController.PageGroup> pages,
            List<TranscriptionController.VisualEvidence> visuals, IgnoreRegion region) {
        return generateMindMap(courseId, groupedAnalysis, segments, pages, visuals);
    }

    default java.util.Map<String,Object> generateSubtitles(String language,
        List<TranscriptionController.TranscriptSegment> segments, List<TranscriptionController.PageGroup> pageGroups,
        String targetLanguage) {
        throw new UnsupportedOperationException("AI subtitles are unavailable");
    }

    default TranscriptionController.MindMapResult generateMindMap(
        List<TranscriptionController.TranscriptSegment> segments,
        List<TranscriptionController.PageGroup> pageGroups) {
        throw new UnsupportedOperationException("Mind-map generation is unavailable");
    }
}

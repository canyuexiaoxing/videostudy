package cn.videostudy.api;

import java.util.List;
import java.util.Map;

@FunctionalInterface
public interface MediaAnalyzer {
    default Map<String,Object> generatePractice(Map<String,Object> source) { throw new UnsupportedOperationException("Practice unavailable"); }
    default Map<String,Object> generateOverview(List<TranscriptionController.TranscriptSegment> segments,
        List<TranscriptionController.PageGroup> pages) { throw new UnsupportedOperationException("Overview unavailable"); }
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

package cn.videostudy.api;

import java.util.List;

@FunctionalInterface
public interface MediaAnalyzer {
    TranscriptionController.TranscriptResult analyze(String fileId, String mode);

    default TranscriptionController.TranscriptResult analyze(String fileId, String mode, String visualAnalysisMode) {
        return analyze(fileId, mode);
    }

    default TranscriptionController.TranscriptResult analyze(String fileId, String mode,
                                                              String visualAnalysisMode, double coarseChangePercent) {
        return analyze(fileId, mode, visualAnalysisMode);
    }

    default TranscriptionController.MindMapResult generateMindMap(
        List<TranscriptionController.TranscriptSegment> segments,
        List<TranscriptionController.PageGroup> pageGroups) {
        throw new UnsupportedOperationException("Mind-map generation is unavailable");
    }
}

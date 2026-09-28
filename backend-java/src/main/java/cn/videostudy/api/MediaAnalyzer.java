package cn.videostudy.api;

@FunctionalInterface
public interface MediaAnalyzer {
    TranscriptionController.TranscriptResult analyze(String fileId, String mode);

    default TranscriptionController.TranscriptResult analyze(String fileId, String mode, String visualAnalysisMode) {
        return analyze(fileId, mode);
    }
}

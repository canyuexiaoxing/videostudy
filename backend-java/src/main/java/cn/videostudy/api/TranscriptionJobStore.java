package cn.videostudy.api;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.List;
import java.time.Instant;
import java.sql.Timestamp;

@Repository
public class TranscriptionJobStore {
    private final JdbcTemplate jdbc;
    private final ObjectMapper json;

    public TranscriptionJobStore(JdbcTemplate jdbc, ObjectMapper json) {
        this.jdbc = jdbc;
        this.json = json;
    }

    public void createQueued(String id) {
        createQueued(id, "both");
    }

    public void createQueued(String id, String visualAnalysisMode) {
        createQueued(id, visualAnalysisMode, 2.0);
    }

    public void createQueued(String id, String visualAnalysisMode, double coarseChangePercent) {
        jdbc.update("INSERT INTO transcription_jobs (id, status, visual_analysis_mode, coarse_change_percent) VALUES (?, 'queued', ?, ?)",
            id, visualAnalysisMode, coarseChangePercent);
    }

    public void createQueued(String id, String visualAnalysisMode, double coarseChangePercent, int sampleSeconds) {
        jdbc.update("INSERT INTO transcription_jobs (id, status, visual_analysis_mode, coarse_change_percent, coarse_sample_seconds) VALUES (?, 'queued', ?, ?, ?)",
            id, visualAnalysisMode, coarseChangePercent, sampleSeconds);
    }

    public void createQueued(String id, String visualMode, double threshold, int sampleSeconds, IgnoreRegion region) {
        if (region == null) { createQueued(id, visualMode, threshold, sampleSeconds); return; }
        try {
            jdbc.update("INSERT INTO transcription_jobs (id, status, visual_analysis_mode, coarse_change_percent, coarse_sample_seconds, ignored_region_json) VALUES (?, 'queued', ?, ?, ?, ?)",
                id, visualMode, threshold, sampleSeconds, json.writeValueAsString(region));
        } catch (JsonProcessingException error) { throw new IllegalStateException("Unable to save ignored region", error); }
    }

    public void saveGroupedAnalysis(String id, boolean groupedAnalysis) {
        requireOne(jdbc.update("UPDATE transcription_jobs SET grouped_analysis = ? WHERE id = ?", groupedAnalysis, id));
    }
    public boolean findGroupedAnalysis(String id) {
        return jdbc.query("SELECT grouped_analysis FROM transcription_jobs WHERE id = ?",
            (row, number) -> row.getBoolean(1), id).stream().findFirst().orElse(false);
    }
    public void saveMindMapMode(String id, String mode) {
        if (!List.of("legacy","grouped","direct").contains(mode)) throw new IllegalArgumentException("Invalid mind map mode");
        requireOne(jdbc.update("UPDATE transcription_jobs SET mind_map_mode = ? WHERE id = ?",mode,id));
    }
    public String findMindMapMode(String id) {
        var modes=jdbc.query("SELECT mind_map_mode FROM transcription_jobs WHERE id = ?",(row,n)->row.getString(1),id);
        var saved=modes.isEmpty()?null:modes.getFirst();
        return saved!=null?saved:findGroupedAnalysis(id)?"grouped":"legacy";
    }
    public void savePersonSelectionMode(String id, String mode) {
        if (!List.of("off","adjacent").contains(mode)) throw new IllegalArgumentException("Invalid person selection mode");
        requireOne(jdbc.update("UPDATE transcription_jobs SET person_selection_mode = ? WHERE id = ?",mode,id));
    }
    public String findPersonSelectionMode(String id) {
        var modes=jdbc.query("SELECT person_selection_mode FROM transcription_jobs WHERE id = ?",(row,n)->row.getString(1),id);
        return modes.isEmpty()?null:modes.getFirst();
    }
    public boolean cancel(String id) {
        return jdbc.update("UPDATE transcription_jobs SET status = 'failed', error_code = 'analysis_cancelled' WHERE id = ? AND status IN ('queued', 'processing')", id) == 1;
    }
    public boolean isCancelled(String id) {
        return find(id).map(job -> "analysis_cancelled".equals(job.error())).orElse(true);
    }

    public record HistoryItem(String id, String name, String status, Instant createdAt) {}

    public void saveOriginalFilename(String id, String filename) {
        var name = filename == null ? "" : filename.replace((char)92, (char)47);
        name = name.substring(name.lastIndexOf('/') + 1).replaceAll("[\\p{Cntrl}]", "").strip();
        if (name.length() > 255) name = name.substring(0, 255);
        requireOne(jdbc.update("UPDATE transcription_jobs SET original_filename = ? WHERE id = ?",
            name.isEmpty() ? null : name, id));
    }

    public List<HistoryItem> listHistory() {
        return jdbc.query("SELECT id, original_filename, status, created_at FROM transcription_jobs ORDER BY created_at DESC, id DESC",
            (row, number) -> new HistoryItem(row.getString("id"), row.getString("original_filename"),
                row.getString("status"), row.getTimestamp("created_at").toInstant()));
    }

    public IgnoreRegion findIgnoredRegion(String id) {
        var values = jdbc.query("SELECT ignored_region_json FROM transcription_jobs WHERE id = ?",
            (row, number) -> row.getString(1), id);
        return values.isEmpty() ? null : IgnoreRegion.parse(values.get(0));
    }

    public int findCoarseSampleSeconds(String id) {
        return jdbc.query("SELECT coarse_sample_seconds FROM transcription_jobs WHERE id = ?",
            (row, number) -> row.getInt(1), id).stream().findFirst().orElse(2);
    }

    public String findVisualAnalysisMode(String id) {
        return jdbc.query("SELECT visual_analysis_mode FROM transcription_jobs WHERE id = ?",
            (row, number) -> row.getString(1), id).stream().findFirst().orElse("both");
    }

    public double findCoarseChangePercent(String id) {
        return jdbc.query("SELECT coarse_change_percent FROM transcription_jobs WHERE id = ?",
            (row, number) -> row.getDouble(1), id).stream().findFirst().orElse(2.0);
    }

    public void markProcessing(String id) {
        requireOne(jdbc.update("UPDATE transcription_jobs SET status = 'processing', error_code = NULL WHERE id = ? AND status = 'queued'", id));
    }

    public void complete(String id, TranscriptionController.TranscriptResult result) {
        try {
            requireOne(jdbc.update("UPDATE transcription_jobs SET status = 'completed', result_json = ?, error_code = NULL WHERE id = ? AND status IN ('queued', 'processing')",
                json.writeValueAsString(result), id));
        } catch (JsonProcessingException error) {
            throw new IllegalStateException("Unable to serialize transcription result", error);
        }
    }

    public void saveMindMap(String id, TranscriptionController.MindMapResult mindMap) {
        var existing = find(id).orElseThrow(() -> new IllegalStateException("Transcription job was not found"));
        if (!"completed".equals(existing.status()) || existing.result() == null)
            throw new IllegalStateException("Cannot update the mind map of an incomplete job");
        try {
            requireOne(jdbc.update("UPDATE transcription_jobs SET result_json = ? WHERE id = ? AND status = 'completed'",
                json.writeValueAsString(existing.result().withMindMap(mindMap)), id));
        } catch (JsonProcessingException error) {
            throw new IllegalStateException("Unable to serialize mind map", error);
        }
    }

    public void markFailed(String id, String errorCode) {
        requireOne(jdbc.update("UPDATE transcription_jobs SET status = 'failed', error_code = ? WHERE id = ? AND (error_code IS NULL OR error_code <> 'analysis_cancelled')", errorCode, id));
    }

    public int recoverInterruptedJobs() {
        return jdbc.update("UPDATE transcription_jobs SET status = 'failed', error_code = 'analysis_interrupted' " +
            "WHERE status IN ('queued', 'processing')");
    }

    public void delete(String id) {
        jdbc.update("DELETE FROM transcription_jobs WHERE id = ?", id);
    }

    public boolean markQueuedIfFailed(String id) {
        return jdbc.update("UPDATE transcription_jobs SET status = 'queued', error_code = NULL WHERE id = ? AND status = 'failed'", id) == 1;
    }

    public List<String> findOldFailedIds(Instant cutoff) {
        return jdbc.query("SELECT id FROM transcription_jobs WHERE (status = 'failed' AND updated_at < ?) OR status = 'expired'",
            (row, number) -> row.getString(1), Timestamp.from(cutoff));
    }

    public List<String> findOldCompletedIds(Instant cutoff) {
        return jdbc.query("SELECT id FROM transcription_jobs WHERE status = 'completed' AND updated_at < ?",
            (row, number) -> row.getString(1), Timestamp.from(cutoff));
    }

    public void markExpired(String id) {
        requireOne(jdbc.update("UPDATE transcription_jobs SET status = 'expired', error_code = 'upload_expired' " +
            "WHERE id = ? AND status IN ('failed', 'expired')", id));
    }

    public Optional<TranscriptionController.TranscriptionJob> find(String id) {
        return jdbc.query("SELECT id, status, result_json, error_code FROM transcription_jobs WHERE id = ?", (row, number) -> {
            var resultJson = row.getString("result_json");
            TranscriptionController.TranscriptResult result = null;
            if (resultJson != null) {
                try {
                    result = json.readValue(resultJson, TranscriptionController.TranscriptResult.class);
                } catch (JsonProcessingException error) {
                    throw new IllegalStateException("Unable to read transcription result", error);
                }
            }
            return new TranscriptionController.TranscriptionJob(row.getString("id"), row.getString("status"),
                result, row.getString("error_code"));
        }, id).stream().findFirst();
    }

    private static void requireOne(int updated) {
        if (updated != 1) throw new IllegalStateException("Transcription job was not found");
    }
}

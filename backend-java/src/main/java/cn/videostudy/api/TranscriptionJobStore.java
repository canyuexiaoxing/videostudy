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

    public String findVisualAnalysisMode(String id) {
        return jdbc.query("SELECT visual_analysis_mode FROM transcription_jobs WHERE id = ?",
            (row, number) -> row.getString(1), id).stream().findFirst().orElse("both");
    }

    public double findCoarseChangePercent(String id) {
        return jdbc.query("SELECT coarse_change_percent FROM transcription_jobs WHERE id = ?",
            (row, number) -> row.getDouble(1), id).stream().findFirst().orElse(2.0);
    }

    public void markProcessing(String id) {
        requireOne(jdbc.update("UPDATE transcription_jobs SET status = 'processing', error_code = NULL WHERE id = ?", id));
    }

    public void complete(String id, TranscriptionController.TranscriptResult result) {
        try {
            requireOne(jdbc.update("UPDATE transcription_jobs SET status = 'completed', result_json = ?, error_code = NULL WHERE id = ?",
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
        requireOne(jdbc.update("UPDATE transcription_jobs SET status = 'failed', error_code = ? WHERE id = ?", errorCode, id));
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

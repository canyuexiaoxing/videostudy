package cn.videostudy.api;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.support.TransactionTemplate;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.*;

/** Source evidence and subtitle state are independent of the main transcript result. */
@Repository
public class SubtitleJobStore {
    private final JdbcTemplate jdbc;
    private final ObjectMapper json;
    private final TransactionTemplate transaction;
    private final SecureRandom random = new SecureRandom();
    public record Source(String language, List<TranscriptionController.TranscriptSegment> segments,
                         List<TranscriptionController.PageGroup> pageGroups) {}
    public record Job(String id, String status, Map<String,Object> result, String error) {}
    public record Key(String id, String targetLanguage) {}
    public record Run(String id, String targetLanguage, String token, int attempt, Source source) {}

    public SubtitleJobStore(JdbcTemplate jdbc, ObjectMapper json) {
        this.jdbc = jdbc; this.json = json;
        this.transaction = new TransactionTemplate(new DataSourceTransactionManager(Objects.requireNonNull(jdbc.getDataSource())));
    }

    public void createUploadRequest(String id, String target) { request(id, target, false); }

    public Job request(String id, String target, boolean retryFailed) {
        return request(id, target, retryFailed, false);
    }
    public Job request(String id, String target, boolean retryFailed, boolean force) {
        return transaction.execute(status -> {
            if (!lockParent(id)) throw new IllegalStateException("Transcription job was not found");
            ensureSource(id);
            var existing = find(id, target);
            if (existing.isEmpty()) {
                var state = source(id).isPresent() ? "queued" : "awaiting_source";
                jdbc.update("INSERT INTO subtitle_jobs (transcription_id, target_language, status) VALUES (?, ?, ?)", id, target, state);
            } else if (retryFailed && ("failed".equals(existing.get().status()) ||
                    List.of("completed", "partial").contains(existing.get().status()) && (force || stale(existing.get().result())))) {
                var state = source(id).isPresent() ? "queued" : "awaiting_source";
                jdbc.update("UPDATE subtitle_jobs SET status = ?, attempt_count = 0, next_attempt_at = NULL, " +
                    "run_token = NULL, result_json = NULL, error_code = NULL WHERE transcription_id = ? AND target_language = ? AND status IN ('failed', 'completed', 'partial')", state, id, target);
            }
            return find(id, target).orElseThrow();
        });
    }
    private static boolean stale(Map<String,Object> result) {
        return result != null && result.get("promptVersion") instanceof String version &&
            !SubtitleResultValidator.PROMPT_VERSION.equals(version);
    }

    private boolean lockParent(String id) {
        return !jdbc.query("SELECT id FROM transcription_jobs WHERE id = ? FOR UPDATE", (row, n) -> row.getString(1), id).isEmpty();
    }
    private void ensureSource(String id) {
        if (callbackToken(id) != null) return;
        var bytes = new byte[32]; random.nextBytes(bytes);
        jdbc.update("INSERT INTO subtitle_sources (transcription_id, callback_token) VALUES (?, ?)", id, HexFormat.of().formatHex(bytes));
    }
    public String callbackToken(String id) {
        return jdbc.query("SELECT callback_token FROM subtitle_sources WHERE transcription_id = ?", (row, n) -> row.getString(1), id)
            .stream().findFirst().orElse(null);
    }

    public boolean captureSource(String id, String token, Source source) {
        return Boolean.TRUE.equals(transaction.execute(status -> {
            if (!lockParent(id)) return false;
            var parentStatus = jdbc.queryForObject("SELECT status FROM transcription_jobs WHERE id = ?", String.class, id);
            if (!List.of("queued", "processing", "completed").contains(parentStatus)) return false;
            var expected = callbackToken(id);
            if (expected == null || token == null || !MessageDigest.isEqual(expected.getBytes(StandardCharsets.UTF_8), token.getBytes(StandardCharsets.UTF_8))) return false;
            saveFirstSource(id, source);
            return true;
        }));
    }

    public void captureFallback(String id, Source source) {
        transaction.executeWithoutResult(status -> {
            if (lockParent(id) && callbackToken(id) != null) {
                // Completed main analysis is authoritative for page understanding.
                // Refresh older snapshots that were captured before that stage.
                validateSource(source);
                jdbc.update("UPDATE subtitle_sources SET source_json = ? WHERE transcription_id = ?", encode(source), id);
                jdbc.update("UPDATE subtitle_jobs SET status = 'queued', error_code = NULL WHERE transcription_id = ? AND status = 'awaiting_source'", id);
            }
        });
    }
    private void saveFirstSource(String id, Source source) {
        validateSource(source);
        jdbc.update("UPDATE subtitle_sources SET source_json = ? WHERE transcription_id = ? AND source_json IS NULL", encode(source), id);
        jdbc.update("UPDATE subtitle_jobs SET status = 'queued', error_code = NULL WHERE transcription_id = ? AND status = 'awaiting_source'", id);
    }
    public static void validateSource(Source source) {
        if (source == null || source.language() == null || source.language().isBlank() || source.segments() == null)
            throw new IllegalArgumentException("Invalid subtitle source");
        var ids = new HashSet<String>();
        for (var segment : source.segments()) {
            if (segment == null || segment.id() == null || !ids.add(segment.id()) || segment.text() == null ||
                segment.startMs() < 0 || segment.endMs() < segment.startMs()) throw new IllegalArgumentException("Invalid subtitle segment");
        }
    }
    public Optional<Source> source(String id) {
        return jdbc.query("SELECT source_json FROM subtitle_sources WHERE transcription_id = ? AND source_json IS NOT NULL",
            (row, n) -> decode(row.getString(1), Source.class), id).stream().findFirst();
    }
    public Optional<Job> find(String id, String target) {
        return jdbc.query("SELECT status, result_json, error_code FROM subtitle_jobs WHERE transcription_id = ? AND target_language = ?",
            (row, n) -> new Job(id, row.getString("status"), decodeMap(row.getString("result_json")), row.getString("error_code")), id, target)
            .stream().findFirst();
    }
    public void discardDuplicatePending(String id, String target) {
        jdbc.update("DELETE FROM subtitle_jobs WHERE transcription_id = ? AND target_language = ? AND status IN ('queued', 'awaiting_source')", id, target);
    }
    public List<Key> due(int limit, int maxAttempts) {
        return jdbc.query("SELECT transcription_id, target_language FROM subtitle_jobs WHERE status = 'queued' AND attempt_count < ? " +
            "AND (next_attempt_at IS NULL OR next_attempt_at <= CURRENT_TIMESTAMP) ORDER BY created_at LIMIT ?",
            (row, n) -> new Key(row.getString(1), row.getString(2)), maxAttempts, limit);
    }
    public Optional<Run> claim(String id, String target, int maxAttempts) {
        return transaction.execute(status -> {
            var token = UUID.randomUUID().toString();
            int count = jdbc.update("UPDATE subtitle_jobs SET status = 'processing', attempt_count = attempt_count + 1, run_token = ?, " +
                "next_attempt_at = NULL WHERE transcription_id = ? AND target_language = ? AND status = 'queued' AND attempt_count < ? " +
                "AND (next_attempt_at IS NULL OR next_attempt_at <= CURRENT_TIMESTAMP)", token, id, target, maxAttempts);
            if (count != 1) return Optional.empty();
            var source = source(id);
            if (source.isEmpty()) throw new IllegalStateException("Subtitle source is unavailable");
            int attempt = jdbc.queryForObject("SELECT attempt_count FROM subtitle_jobs WHERE transcription_id = ? AND target_language = ?", Integer.class, id, target);
            return Optional.of(new Run(id, target, token, attempt, source.get()));
        });
    }
    public boolean finish(Run run, Map<String,Object> result, String state, String error) {
        return jdbc.update("UPDATE subtitle_jobs SET status = ?, result_json = ?, error_code = ?, run_token = NULL, next_attempt_at = NULL " +
            "WHERE transcription_id = ? AND target_language = ? AND status = 'processing' AND run_token = ?",
            state, result == null ? null : encode(result), error, run.id(), run.targetLanguage(), run.token()) == 1;
    }
    public void retry(Run run, Instant when) {
        jdbc.update("UPDATE subtitle_jobs SET status = 'queued', run_token = NULL, next_attempt_at = ?, error_code = 'subtitle_temporarily_unavailable' " +
            "WHERE transcription_id = ? AND target_language = ? AND status = 'processing' AND run_token = ?",
            Timestamp.from(when), run.id(), run.targetLanguage(), run.token());
    }
    public int recoverInterrupted(int maxAttempts) {
        return transaction.execute(status -> {
            int failed = jdbc.update("UPDATE subtitle_jobs SET status = 'failed', run_token = NULL, error_code = 'subtitle_interrupted' " +
                "WHERE status = 'processing' AND attempt_count >= ?", maxAttempts);
            int queued = jdbc.update("UPDATE subtitle_jobs SET status = 'queued', run_token = NULL, next_attempt_at = NULL, error_code = NULL " +
                "WHERE status = 'processing' AND attempt_count < ?", maxAttempts);
            return failed + queued;
        });
    }
    public void sourceUnavailable(String id) {
        jdbc.update("UPDATE subtitle_jobs SET status = 'failed', error_code = 'subtitle_source_unavailable' " +
            "WHERE transcription_id = ? AND status = 'awaiting_source'", id);
    }
    public void failUnavailableSources() {
        jdbc.update("UPDATE subtitle_jobs SET status = 'failed', error_code = 'subtitle_source_unavailable' " +
            "WHERE status = 'awaiting_source' AND transcription_id IN " +
            "(SELECT id FROM transcription_jobs WHERE status = 'failed')");
    }
    private String encode(Object value) {
        try { return json.writeValueAsString(value); }
        catch (JsonProcessingException error) { throw new IllegalStateException("Unable to serialize subtitle data", error); }
    }
    private <T> T decode(String value, Class<T> type) {
        try { return json.readValue(value, type); }
        catch (JsonProcessingException error) { throw new IllegalStateException("Unable to read subtitle data", error); }
    }
    private Map<String,Object> decodeMap(String value) {
        if (value == null) return null;
        try { return json.readValue(value, new TypeReference<Map<String,Object>>() {}); }
        catch (JsonProcessingException error) { throw new IllegalStateException("Unable to read subtitle result", error); }
    }
}

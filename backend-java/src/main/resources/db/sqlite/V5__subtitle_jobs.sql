CREATE TABLE subtitle_sources (
    transcription_id CHAR(36) NOT NULL PRIMARY KEY,
    callback_token CHAR(64) NOT NULL,
    source_json LONGTEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now')),
    updated_at TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now')),
    CONSTRAINT fk_subtitle_source_job FOREIGN KEY (transcription_id) REFERENCES transcription_jobs(id) ON DELETE CASCADE
);

CREATE TABLE subtitle_jobs (
    transcription_id CHAR(36) NOT NULL,
    target_language VARCHAR(12) NOT NULL,
    status VARCHAR(24) NOT NULL,
    attempt_count INT NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMP NULL,
    run_token CHAR(36) NULL,
    result_json LONGTEXT NULL,
    error_code VARCHAR(64) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now')),
    updated_at TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now')),
    PRIMARY KEY (transcription_id, target_language),
    CONSTRAINT fk_subtitle_target_job FOREIGN KEY (transcription_id) REFERENCES transcription_jobs(id) ON DELETE CASCADE
);
CREATE INDEX idx_subtitle_dispatch ON subtitle_jobs(status, next_attempt_at);

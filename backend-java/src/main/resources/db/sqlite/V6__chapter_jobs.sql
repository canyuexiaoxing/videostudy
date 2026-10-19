CREATE TABLE chapter_jobs (
    transcription_id CHAR(36) NOT NULL PRIMARY KEY,
    status VARCHAR(24) NOT NULL,
    attempt_count INT NOT NULL DEFAULT 0,
    run_token CHAR(36) NULL,
    result_json LONGTEXT NULL,
    error_code VARCHAR(64) NULL,
    CONSTRAINT fk_chapter_job FOREIGN KEY (transcription_id) REFERENCES transcription_jobs(id) ON DELETE CASCADE
);

CREATE TABLE practice_sets (
    id CHAR(36) NOT NULL PRIMARY KEY,
    transcription_id CHAR(36) NOT NULL,
    source_hash CHAR(64) NOT NULL,
    request_key CHAR(64) NOT NULL,
    scope_title VARCHAR(200) NOT NULL,
    status VARCHAR(24) NOT NULL,
    source_json LONGTEXT NOT NULL,
    result_json LONGTEXT NULL,
    error_code VARCHAR(64) NULL,
    attempt_count INT NOT NULL DEFAULT 0,
    run_token CHAR(36) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now')),
    UNIQUE (transcription_id, request_key),
    CONSTRAINT fk_practice_analysis FOREIGN KEY (transcription_id) REFERENCES transcription_jobs(id) ON DELETE CASCADE
);
CREATE TABLE practice_sessions (
    id CHAR(36) NOT NULL PRIMARY KEY,
    set_id CHAR(36) NOT NULL,
    client_id CHAR(36) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now')),
    CONSTRAINT fk_practice_session FOREIGN KEY (set_id) REFERENCES practice_sets(id) ON DELETE CASCADE
);
CREATE TABLE practice_answers (
    session_id CHAR(36) NOT NULL,
    question_id CHAR(36) NOT NULL,
    selected_index INT NOT NULL,
    correct BOOLEAN NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now')),
    PRIMARY KEY (session_id, question_id),
    CONSTRAINT fk_practice_answer FOREIGN KEY (session_id) REFERENCES practice_sessions(id) ON DELETE CASCADE
);
CREATE INDEX idx_practice_pending ON practice_sets(status);
CREATE INDEX idx_practice_client ON practice_sessions(set_id, client_id);

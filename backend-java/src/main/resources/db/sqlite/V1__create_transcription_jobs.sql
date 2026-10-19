CREATE TABLE transcription_jobs (
    id CHAR(36) NOT NULL PRIMARY KEY,
    status VARCHAR(24) NOT NULL,
    result_json LONGTEXT NULL,
    error_code VARCHAR(64) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now')),
    updated_at TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now'))
);

CREATE TABLE cloud_sync_documents (
 owner_id VARCHAR(64) NOT NULL,
 course_id CHAR(36) NOT NULL,
 revision BIGINT NOT NULL,
 content_hash CHAR(64) NOT NULL,
 payload_json LONGTEXT NOT NULL,
 updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 PRIMARY KEY(owner_id,course_id)
);

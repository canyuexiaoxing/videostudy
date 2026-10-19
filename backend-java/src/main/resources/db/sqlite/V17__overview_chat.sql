CREATE TABLE overview_chat_threads (
 id CHAR(36) NOT NULL PRIMARY KEY,
 transcription_id CHAR(36) NOT NULL,
 context_key VARCHAR(64) NOT NULL,
 client_id CHAR(36) NOT NULL,
 lock_token CHAR(36) NULL,
 lock_until BIGINT NOT NULL DEFAULT 0,
 UNIQUE (transcription_id,context_key,client_id),
 CONSTRAINT fk_overview_chat_course FOREIGN KEY (transcription_id) REFERENCES transcription_jobs(id) ON DELETE CASCADE
);
CREATE TABLE overview_chat_turns (
 id CHAR(36) NOT NULL PRIMARY KEY,
 thread_id CHAR(36) NOT NULL,
 request_id CHAR(36) NOT NULL,
 user_text VARCHAR(2000) NOT NULL,
 reply_json LONGTEXT NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now')),
 UNIQUE(thread_id,request_id),
 CONSTRAINT fk_overview_chat_thread FOREIGN KEY(thread_id) REFERENCES overview_chat_threads(id) ON DELETE CASCADE
);

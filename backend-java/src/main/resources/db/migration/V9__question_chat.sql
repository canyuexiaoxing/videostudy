CREATE TABLE question_chat_threads (
    id CHAR(36) NOT NULL PRIMARY KEY,
    set_id CHAR(36) NOT NULL,
    question_id CHAR(36) NOT NULL,
    client_id CHAR(36) NOT NULL,
    lock_token CHAR(36) NULL,
    lock_until BIGINT NOT NULL DEFAULT 0,
    UNIQUE (set_id, question_id, client_id),
    CONSTRAINT fk_question_chat_set FOREIGN KEY (set_id) REFERENCES practice_sets(id) ON DELETE CASCADE
);
CREATE TABLE question_chat_turns (
    id CHAR(36) NOT NULL PRIMARY KEY,
    thread_id CHAR(36) NOT NULL,
    request_id CHAR(36) NOT NULL,
    user_text VARCHAR(2000) NOT NULL,
    reply_json LONGTEXT NOT NULL,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    UNIQUE (thread_id, request_id),
    CONSTRAINT fk_question_chat_thread FOREIGN KEY (thread_id) REFERENCES question_chat_threads(id) ON DELETE CASCADE
);

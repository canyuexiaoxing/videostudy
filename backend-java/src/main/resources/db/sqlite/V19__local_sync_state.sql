CREATE TABLE local_sync_state (
 course_id TEXT NOT NULL PRIMARY KEY,
 remote_revision INTEGER NOT NULL,
 base_hash TEXT NOT NULL,
 synced_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now')),
 FOREIGN KEY(course_id) REFERENCES transcription_jobs(id) ON DELETE CASCADE
);

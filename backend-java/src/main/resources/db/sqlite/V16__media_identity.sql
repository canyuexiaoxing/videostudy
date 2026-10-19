ALTER TABLE transcription_jobs ADD COLUMN media_size BIGINT NULL;
ALTER TABLE transcription_jobs ADD COLUMN media_fingerprint VARCHAR(64) NULL;

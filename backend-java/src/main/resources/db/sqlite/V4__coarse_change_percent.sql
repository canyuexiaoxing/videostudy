ALTER TABLE transcription_jobs
    ADD COLUMN coarse_change_percent DECIMAL(3,1) NOT NULL DEFAULT 3.0;

ALTER TABLE transcription_jobs
    ADD COLUMN visual_analysis_mode VARCHAR(16) NOT NULL DEFAULT 'both';

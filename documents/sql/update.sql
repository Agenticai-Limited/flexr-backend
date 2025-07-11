-- Add page_id field to low_relevance_results table
ALTER TABLE low_relevance_results ADD COLUMN IF NOT EXISTS page_id TEXT;
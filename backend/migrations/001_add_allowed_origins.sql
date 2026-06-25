-- Run in Supabase SQL Editor (Dashboard → SQL → New query)
-- Adds per-chatbot origin whitelist for the embeddable widget.

ALTER TABLE chatbots
  ADD COLUMN IF NOT EXISTS allowed_origins text[] NOT NULL DEFAULT '{}';

-- Backfill existing chatbots: website origin + keep empty-array rows as allow-all
UPDATE chatbots
SET allowed_origins = ARRAY[
  regexp_replace(website_url, '^(https?://[^/]+).*$', '\1')
]
WHERE (allowed_origins IS NULL OR allowed_origins = '{}')
  AND website_url IS NOT NULL
  AND website_url ~ '^https?://';

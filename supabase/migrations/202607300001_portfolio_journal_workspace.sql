-- User-owned annotations for the paper-trading journal. Trading and risk fields are unchanged.
alter table public.paper_trades add column if not exists journal_notes text;
alter table public.paper_trades add column if not exists setup_tags jsonb not null default '[]'::jsonb;
alter table public.paper_trades add column if not exists mistake_tags jsonb not null default '[]'::jsonb;
alter table public.paper_trades add column if not exists emotion_tags jsonb not null default '[]'::jsonb;
alter table public.paper_trades add column if not exists confidence_before numeric check (confidence_before between 0 and 100);
alter table public.paper_trades add column if not exists confidence_after numeric check (confidence_after between 0 and 100);
alter table public.paper_trades add column if not exists screenshot_url text;
alter table public.paper_trades add column if not exists lessons_learned text;
alter table public.paper_trades add column if not exists review_completed boolean not null default false;
alter table public.paper_trades add column if not exists exit_reason text;
alter table public.paper_trades add column if not exists journal_updated_at timestamptz;

-- Existing "paper trades own records" RLS policy remains authoritative. The API also
-- scopes every read and update to auth.uid(); no browser-supplied user_id is accepted.

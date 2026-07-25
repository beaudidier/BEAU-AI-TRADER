-- S&P 500 rollout diagnostics and resumable checkpoints for paper-only validation.
alter table public.forward_validation_runs
  add column if not exists universe_id text not null default 'demo',
  add column if not exists universe_snapshot_version text,
  add column if not exists expected_symbols integer not null default 10
    check (expected_symbols >= 0),
  add column if not exists scanned_symbols integer not null default 0
    check (scanned_symbols >= 0),
  add column if not exists cached_symbols integer not null default 0
    check (cached_symbols >= 0),
  add column if not exists provider_request_count integer not null default 0
    check (provider_request_count >= 0),
  add column if not exists retry_count integer not null default 0
    check (retry_count >= 0),
  add column if not exists runtime_seconds numeric not null default 0
    check (runtime_seconds >= 0),
  add column if not exists batches_completed integer not null default 0
    check (batches_completed >= 0),
  add column if not exists total_batches integer not null default 0
    check (total_batches >= 0),
  add column if not exists completion_percentage numeric not null default 0
    check (completion_percentage >= 0 and completion_percentage <= 100),
  add column if not exists provider_health text not null default 'waiting'
    check (provider_health in ('waiting', 'running', 'healthy', 'degraded', 'failed')),
  add column if not exists last_complete_market_date date,
  add column if not exists rejection_reasons jsonb not null default '{}'::jsonb,
  add column if not exists checkpoint jsonb not null default '{}'::jsonb,
  add column if not exists resumed_from_run_id uuid
    references public.forward_validation_runs(id) on delete set null;

update public.forward_validation_runs
set
  scanned_symbols = cardinality(symbols_completed),
  expected_symbols = greatest(cardinality(symbols_requested), 0),
  completion_percentage = case
    when cardinality(symbols_requested) = 0 then 100
    else round(
      cardinality(symbols_completed)::numeric
      / cardinality(symbols_requested)::numeric
      * 100,
      2
    )
  end,
  provider_health = case status
    when 'success' then 'healthy'
    when 'partial' then 'degraded'
    when 'failed' then 'failed'
    when 'running' then 'running'
    else 'waiting'
  end
where universe_snapshot_version is null;

alter table public.forward_validation_runs
  alter column universe_id set default 'sp500',
  alter column expected_symbols set default 503,
  alter column provider_health set default 'running';

create index if not exists forward_validation_runs_resume_idx
  on public.forward_validation_runs (
    user_id,
    universe_snapshot_version,
    started_at desc
  );

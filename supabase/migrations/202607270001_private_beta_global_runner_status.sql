-- Private-beta members may read sanitized global runner diagnostics.
-- User-owned signals, outcomes, paper trades, and portfolio records remain isolated.
create or replace function public.private_beta_runner_runs()
returns table (
  runner_version text,
  trigger text,
  status text,
  started_at timestamptz,
  completed_at timestamptz,
  data_timestamp timestamptz,
  signals_created integer,
  duplicates_prevented integer,
  outcomes_updated integer,
  universe_id text,
  universe_snapshot_version text,
  expected_symbols integer,
  eligible_symbols text[],
  completed_eligible_symbols text[],
  excluded_symbols jsonb,
  genuine_failures jsonb,
  scanned_symbols integer,
  cached_symbols integer,
  provider_request_count integer,
  retry_count integer,
  runtime_seconds numeric,
  batches_completed integer,
  total_batches integer,
  completion_percentage numeric,
  provider_health text,
  last_complete_market_date date,
  rejection_reasons jsonb
)
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select
    runs.runner_version,
    runs.trigger,
    runs.status,
    runs.started_at,
    runs.completed_at,
    runs.data_timestamp,
    runs.signals_created,
    runs.duplicates_prevented,
    runs.outcomes_updated,
    runs.universe_id,
    runs.universe_snapshot_version,
    runs.expected_symbols,
    runs.eligible_symbols,
    runs.completed_eligible_symbols,
    runs.excluded_symbols,
    runs.genuine_failures,
    runs.scanned_symbols,
    runs.cached_symbols,
    runs.provider_request_count,
    runs.retry_count,
    runs.runtime_seconds,
    runs.batches_completed,
    runs.total_batches,
    runs.completion_percentage,
    runs.provider_health,
    runs.last_complete_market_date,
    runs.rejection_reasons
  from public.forward_validation_runs as runs
  where exists (
    select 1
    from public.private_beta_memberships as membership
    where membership.user_id = auth.uid()
      and membership.active
  )
  order by runs.started_at desc
  limit 20;
$$;

revoke all on function public.private_beta_runner_runs() from public;
revoke all on function public.private_beta_runner_runs() from anon;
grant execute on function public.private_beta_runner_runs() to authenticated;

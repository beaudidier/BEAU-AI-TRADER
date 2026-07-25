-- Operational ledger and lifecycle fields for the automated paper-only runner.
alter table public.forward_validation_signals
  add column if not exists expiry_date date,
  add column if not exists initial_status text not null default 'waiting_for_entry'
    check (initial_status = 'waiting_for_entry');

alter table public.forward_validation_outcomes
  drop constraint if exists forward_validation_outcomes_status_check;

update public.forward_validation_outcomes
set status = case status
  when 'ACTIVE' then 'waiting_for_entry'
  when 'EXPIRED' then 'expired'
  when 'OPEN' then 'entered'
  when 'COMPLETED' then 'completed'
  else status
end;

alter table public.forward_validation_outcomes
  add constraint forward_validation_outcomes_status_check
    check (status in (
      'waiting_for_entry',
      'entered',
      'expired',
      'TP1_hit',
      'TP2_hit',
      'stopped',
      'completed',
      'data_error'
    )),
  add column if not exists open_r numeric not null default 0,
  add column if not exists mfe_r numeric not null default 0,
  add column if not exists mae_r numeric not null default 0,
  add column if not exists last_evaluated_at timestamptz;

create table if not exists public.forward_validation_runs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  runner_version text not null,
  trigger text not null check (trigger in ('manual', 'scheduled')),
  status text not null check (status in ('running', 'success', 'partial', 'failed', 'skipped')),
  started_at timestamptz not null,
  completed_at timestamptz,
  data_timestamp timestamptz,
  symbols_requested text[] not null default '{}',
  symbols_completed text[] not null default '{}',
  symbols_failed text[] not null default '{}',
  provider_errors jsonb not null default '{}'::jsonb,
  signals_created integer not null default 0 check (signals_created >= 0),
  duplicates_prevented integer not null default 0 check (duplicates_prevented >= 0),
  outcomes_updated integer not null default 0 check (outcomes_updated >= 0),
  message text,
  created_at timestamptz not null default now()
);

create index if not exists forward_validation_runs_user_started_idx
  on public.forward_validation_runs (user_id, started_at desc);

alter table public.paper_trades
  add column if not exists market_price numeric,
  add column if not exists unrealized_pnl numeric,
  add column if not exists quote_timestamp timestamptz;

alter table public.forward_validation_runs enable row level security;

drop policy if exists "forward validation runs own select" on public.forward_validation_runs;
create policy "forward validation runs own select"
  on public.forward_validation_runs for select
  using (user_id = auth.uid());

drop policy if exists "forward validation runs own insert" on public.forward_validation_runs;
create policy "forward validation runs own insert"
  on public.forward_validation_runs for insert
  with check (user_id = auth.uid());

drop policy if exists "forward validation runs own update" on public.forward_validation_runs;
create policy "forward validation runs own update"
  on public.forward_validation_runs for update
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

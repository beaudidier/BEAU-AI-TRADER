-- Immutable paper-only signal snapshots for the frozen Regime-Gated Pullback.
create table if not exists public.forward_validation_signals (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  ticker text not null,
  signal_timestamp timestamptz not null,
  signal_price numeric not null check (signal_price > 0),
  proposed_pullback_entry numeric not null check (proposed_pullback_entry > 0),
  expected_entry_fill numeric not null check (expected_entry_fill > 0),
  stop_loss numeric not null check (stop_loss > 0),
  target_1 numeric not null check (target_1 > 0),
  target_2 numeric not null check (target_2 > target_1),
  market_regime text not null,
  market_regime_score numeric not null,
  confidence numeric not null check (confidence between 0 and 100),
  strategy_version text not null,
  data_timestamp timestamptz not null,
  created_at timestamptz not null default now(),
  unique (user_id, ticker, strategy_version, data_timestamp)
);

create table if not exists public.forward_validation_outcomes (
  signal_id uuid primary key references public.forward_validation_signals(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  status text not null default 'ACTIVE' check (status in ('ACTIVE', 'EXPIRED', 'OPEN', 'COMPLETED')),
  entry_price numeric,
  entry_timestamp timestamptz,
  completed_at timestamptz,
  tp1_hit boolean not null default false,
  tp2_hit boolean not null default false,
  stop_hit boolean not null default false,
  open_pl numeric not null default 0,
  realized_r numeric not null default 0,
  double_cost_realized_r numeric,
  holding_days integer not null default 0,
  costs numeric not null default 0,
  slippage numeric not null default 0,
  remaining_fraction numeric not null default 1,
  updated_at timestamptz not null default now()
);

create index if not exists forward_validation_signals_user_created_idx on public.forward_validation_signals (user_id, created_at desc);
create index if not exists forward_validation_outcomes_user_status_idx on public.forward_validation_outcomes (user_id, status);

create or replace function public.prevent_forward_validation_signal_mutation()
returns trigger language plpgsql as $$
begin
  raise exception 'Forward-validation signal snapshots are immutable';
end;
$$;

drop trigger if exists forward_validation_signals_immutable on public.forward_validation_signals;
create trigger forward_validation_signals_immutable
before update or delete on public.forward_validation_signals
for each row execute procedure public.prevent_forward_validation_signal_mutation();

create trigger forward_validation_outcomes_updated_at
before update on public.forward_validation_outcomes
for each row execute procedure public.set_updated_at();

alter table public.forward_validation_signals enable row level security;
alter table public.forward_validation_outcomes enable row level security;

create policy "forward validation signals own select" on public.forward_validation_signals for select using (user_id = auth.uid());
create policy "forward validation signals own insert" on public.forward_validation_signals for insert with check (user_id = auth.uid());
create policy "forward validation outcomes own records" on public.forward_validation_outcomes for all using (user_id = auth.uid()) with check (user_id = auth.uid());

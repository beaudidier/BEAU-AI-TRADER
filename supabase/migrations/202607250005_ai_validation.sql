create table if not exists public.recommendation_validations (
  id uuid primary key default gen_random_uuid(),
  ticker text not null,
  confidence numeric not null check (confidence between 0 and 100),
  verdict text not null,
  timestamp timestamptz not null default now(),
  entry numeric not null,
  stop numeric not null,
  target numeric not null,
  market_regime text not null,
  evaluations jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists recommendation_validations_ticker_timestamp_idx on public.recommendation_validations (ticker, timestamp desc);

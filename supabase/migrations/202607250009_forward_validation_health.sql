-- Accurate coverage health and explicit per-symbol outcome diagnostics.
alter table public.forward_validation_runs
  add column if not exists eligible_symbols text[] not null default '{}',
  add column if not exists completed_eligible_symbols text[] not null default '{}',
  add column if not exists excluded_symbols jsonb not null default '{}'::jsonb,
  add column if not exists genuine_failures jsonb not null default '{}'::jsonb,
  add column if not exists symbol_outcomes jsonb not null default '{}'::jsonb;

update public.forward_validation_runs
set
  eligible_symbols = symbols_completed,
  completed_eligible_symbols = symbols_completed,
  completion_percentage = case
    when expected_symbols = 0 then 100
    else round(
      cardinality(symbols_completed)::numeric
      / expected_symbols::numeric
      * 100,
      2
    )
  end,
  provider_health = case
    when expected_symbols = 0 then 'healthy'
    when cardinality(symbols_completed)::numeric / expected_symbols >= 0.95
      then 'healthy'
    when cardinality(symbols_completed)::numeric / expected_symbols >= 0.90
      then 'degraded'
    else 'failed'
  end,
  status = case
    when expected_symbols = 0 then 'success'
    when cardinality(symbols_completed)::numeric / expected_symbols >= 0.95
      then 'success'
    when cardinality(symbols_completed)::numeric / expected_symbols >= 0.90
      then 'partial'
    else 'failed'
  end
where status in ('success', 'partial', 'failed');

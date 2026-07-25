-- Validated paper-only portfolio admission limits from Milestones 47-48.
-- No broker or real-money execution is introduced.

alter table public.paper_trades
  add column if not exists initial_risk_amount numeric,
  add column if not exists initial_risk_r numeric,
  add column if not exists remaining_risk_r numeric,
  add column if not exists remaining_fraction numeric not null default 1,
  add column if not exists risk_admitted_at timestamptz,
  add column if not exists trade_source text not null default 'manual',
  add column if not exists forward_validation_signal_id uuid
    references public.forward_validation_signals(id) on delete set null,
  add column if not exists portfolio_signal_rank integer;

insert into public.paper_accounts (user_id)
select distinct user_id from public.paper_trades
on conflict (user_id) do nothing;

update public.paper_trades as trade
set
  initial_risk_amount = coalesce(
    trade.initial_risk_amount,
    greatest(0, (trade.entry_price - trade.stop_loss) * trade.quantity)
  ),
  initial_risk_r = coalesce(
    trade.initial_risk_r,
    greatest(0, (trade.entry_price - trade.stop_loss) * trade.quantity)
      / greatest(0.01, account.initial_balance * 0.01)
  ),
  remaining_risk_r = case
    when trade.status = 'CLOSED' then 0
    else coalesce(
      trade.remaining_risk_r,
      greatest(0, (trade.entry_price - trade.stop_loss) * trade.quantity)
        / greatest(0.01, account.initial_balance * 0.01)
    )
  end,
  risk_admitted_at = coalesce(trade.risk_admitted_at, trade.opened_at)
from public.paper_accounts as account
where account.user_id = trade.user_id;

alter table public.paper_trades
  alter column initial_risk_amount set not null,
  alter column initial_risk_r set not null,
  alter column remaining_risk_r set not null,
  alter column risk_admitted_at set not null;

alter table public.paper_trades
  drop constraint if exists paper_trades_trade_source_check;
alter table public.paper_trades
  add constraint paper_trades_trade_source_check
  check (trade_source in ('manual', 'forward_validation'));

create unique index if not exists paper_trades_forward_signal_unique
  on public.paper_trades (forward_validation_signal_id)
  where forward_validation_signal_id is not null;

alter table public.forward_validation_signals
  add column if not exists portfolio_signal_rank integer;

alter table public.forward_validation_outcomes
  drop constraint if exists forward_validation_outcomes_status_check;
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
    'data_error',
    'portfolio_blocked'
  ));

create table if not exists public.portfolio_risk_rejections (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  deduplication_key text not null,
  source text not null check (
    source in (
      'forward_validation_signal',
      'paper_trade_automatic',
      'paper_trade_manual'
    )
  ),
  ticker text not null,
  signal_id uuid references public.forward_validation_signals(id)
    on delete set null,
  rejection_reason text not null,
  current_open_positions integer not null check (current_open_positions >= 0),
  current_open_risk_r numeric not null check (current_open_risk_r >= 0),
  daily_new_risk_r numeric not null check (daily_new_risk_r >= 0),
  proposed_risk_r numeric not null check (proposed_risk_r >= 0),
  signal_rank integer not null check (signal_rank > 0),
  limiting_reference text,
  capacity_resets_at timestamptz not null,
  signal_snapshot jsonb not null default '{}'::jsonb,
  rejected_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index if not exists portfolio_risk_rejections_user_time_idx
  on public.portfolio_risk_rejections (user_id, rejected_at desc);

create unique index if not exists portfolio_risk_rejections_signal_source_unique
  on public.portfolio_risk_rejections (user_id, source, signal_id)
  where signal_id is not null;

create unique index if not exists portfolio_risk_rejections_dedupe_unique
  on public.portfolio_risk_rejections (
    user_id,
    source,
    deduplication_key
  );

alter table public.portfolio_risk_rejections enable row level security;

drop policy if exists "portfolio risk rejections own select"
  on public.portfolio_risk_rejections;
create policy "portfolio risk rejections own select"
  on public.portfolio_risk_rejections for select
  using (user_id = auth.uid());

drop policy if exists "portfolio risk rejections own insert"
  on public.portfolio_risk_rejections;
create policy "portfolio risk rejections own insert"
  on public.portfolio_risk_rejections for insert
  with check (user_id = auth.uid());

create or replace function public.open_validated_paper_trade(
  p_user_id uuid,
  p_ticker text,
  p_side text,
  p_entry_price numeric,
  p_stop_loss numeric,
  p_target_1 numeric,
  p_target_2 numeric,
  p_quantity numeric,
  p_confidence_score numeric,
  p_recommendation text,
  p_setup_quality text,
  p_market_regime text,
  p_trend text,
  p_momentum text,
  p_sector text,
  p_source text,
  p_signal_id uuid,
  p_signal_rank integer,
  p_risk_admitted_at timestamptz
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  account public.paper_accounts;
  existing_trade public.paper_trades;
  created_trade public.paper_trades;
  notional numeric;
  risk_unit numeric;
  proposed_risk_amount numeric;
  proposed_risk_r numeric;
  open_positions integer;
  open_risk_r numeric;
  daily_new_risk_r numeric;
  reasons text[] := '{}';
  reason_text text;
  reset_at timestamptz;
  limiting_positions jsonb;
begin
  if auth.uid() is null and auth.role() <> 'service_role' then
    raise exception 'Authentication required';
  end if;
  if auth.role() <> 'service_role' and auth.uid() <> p_user_id then
    raise exception 'Paper account access denied';
  end if;
  if p_side <> 'BUY' or p_entry_price <= 0 or p_quantity <= 0 then
    raise exception 'Only validated long paper buys are supported';
  end if;
  if p_stop_loss <= 0 or p_stop_loss >= p_entry_price
     or p_target_1 <= p_entry_price or p_target_2 <= p_target_1 then
    raise exception 'Invalid long paper-trade levels';
  end if;
  if p_source not in ('manual', 'forward_validation') then
    raise exception 'Invalid paper-trade source';
  end if;
  if p_signal_rank is null or p_signal_rank <= 0 then
    raise exception 'A positive signal rank is required';
  end if;

  if p_signal_id is not null then
    select * into existing_trade
    from public.paper_trades
    where forward_validation_signal_id = p_signal_id;
    if found then
      return to_jsonb(existing_trade);
    end if;
  end if;

  insert into public.paper_accounts (user_id)
  values (p_user_id)
  on conflict (user_id) do nothing;

  select * into account
  from public.paper_accounts
  where user_id = p_user_id
  for update;

  risk_unit := greatest(0.01, account.initial_balance * 0.01);
  proposed_risk_amount :=
    greatest(0, (p_entry_price - p_stop_loss) * p_quantity);
  proposed_risk_r := proposed_risk_amount / risk_unit;
  notional := p_entry_price * p_quantity;
  reset_at := (
    date_trunc('day', timezone('America/New_York', p_risk_admitted_at))
    + interval '1 day'
  ) at time zone 'America/New_York';

  select
    count(*),
    coalesce(sum(remaining_risk_r), 0),
    coalesce(
      jsonb_agg(
        jsonb_build_object(
          'id', id,
          'ticker', ticker,
          'remaining_risk_r', remaining_risk_r
        )
        order by remaining_risk_r desc, opened_at, ticker
      ),
      '[]'::jsonb
    )
  into open_positions, open_risk_r, limiting_positions
  from public.paper_trades
  where user_id = p_user_id and status = 'OPEN';

  select coalesce(sum(initial_risk_r), 0)
  into daily_new_risk_r
  from public.paper_trades
  where user_id = p_user_id
    and timezone('America/New_York', risk_admitted_at)::date
      = timezone('America/New_York', p_risk_admitted_at)::date;

  if open_positions + 1 > 10 then
    reasons := array_append(
      reasons,
      format('Opening %s would exceed the 10-position limit.', upper(p_ticker))
    );
  end if;
  if open_risk_r + proposed_risk_r > 10.000000001 then
    reasons := array_append(
      reasons,
      format('Opening %s would exceed the 10R open-risk limit.', upper(p_ticker))
    );
  end if;
  if daily_new_risk_r + proposed_risk_r > 1.000000001 then
    reasons := array_append(
      reasons,
      format(
        'Opening %s would exceed today''s 1R new-risk budget.',
        upper(p_ticker)
      )
    );
  end if;

  if cardinality(reasons) > 0 then
    reason_text := array_to_string(reasons, ' ');
    insert into public.portfolio_risk_rejections (
      user_id,
      deduplication_key,
      source,
      ticker,
      signal_id,
      rejection_reason,
      current_open_positions,
      current_open_risk_r,
      daily_new_risk_r,
      proposed_risk_r,
      signal_rank,
      limiting_reference,
      capacity_resets_at,
      signal_snapshot,
      rejected_at
    ) values (
      p_user_id,
      coalesce(p_signal_id::text, gen_random_uuid()::text),
      case
        when p_source = 'forward_validation'
          then 'paper_trade_automatic'
        else 'paper_trade_manual'
      end,
      upper(p_ticker),
      p_signal_id,
      reason_text,
      open_positions,
      open_risk_r,
      daily_new_risk_r,
      proposed_risk_r,
      p_signal_rank,
      coalesce(limiting_positions -> 0 ->> 'ticker', 'daily risk budget'),
      reset_at,
      jsonb_build_object(
        'entry_price', p_entry_price,
        'stop_loss', p_stop_loss,
        'target_1', p_target_1,
        'target_2', p_target_2,
        'confidence', p_confidence_score,
        'recommendation', p_recommendation
      ),
      p_risk_admitted_at
    )
    on conflict (user_id, source, signal_id)
      where signal_id is not null
    do nothing;

    return jsonb_build_object(
      'blocked', true,
      'rejection_reason', reason_text,
      'current_open_positions', open_positions,
      'current_open_risk_r', open_risk_r,
      'daily_new_risk_r', daily_new_risk_r,
      'proposed_risk_r', proposed_risk_r,
      'signal_rank', p_signal_rank,
      'capacity_resets_at', reset_at,
      'limiting_positions', limiting_positions
    );
  end if;

  if account.cash_balance < notional then
    raise exception 'Insufficient paper trading cash';
  end if;

  update public.paper_accounts
  set cash_balance = cash_balance - notional
  where user_id = p_user_id;

  insert into public.paper_trades (
    user_id,
    ticker,
    side,
    entry_price,
    stop_loss,
    target_1,
    target_2,
    quantity,
    confidence_score,
    recommendation,
    setup_quality,
    market_regime,
    trend,
    momentum,
    sector,
    initial_risk_amount,
    initial_risk_r,
    remaining_risk_r,
    remaining_fraction,
    risk_admitted_at,
    trade_source,
    forward_validation_signal_id,
    portfolio_signal_rank,
    opened_at
  ) values (
    p_user_id,
    upper(p_ticker),
    'BUY',
    p_entry_price,
    p_stop_loss,
    p_target_1,
    p_target_2,
    p_quantity,
    p_confidence_score,
    p_recommendation,
    p_setup_quality,
    p_market_regime,
    p_trend,
    p_momentum,
    p_sector,
    proposed_risk_amount,
    proposed_risk_r,
    proposed_risk_r,
    1,
    p_risk_admitted_at,
    p_source,
    p_signal_id,
    p_signal_rank,
    p_risk_admitted_at
  )
  returning * into created_trade;

  return to_jsonb(created_trade);
end;
$$;

create or replace function public.open_paper_trade(
  p_ticker text,
  p_side text,
  p_entry_price numeric,
  p_stop_loss numeric,
  p_target_1 numeric,
  p_target_2 numeric,
  p_quantity numeric,
  p_confidence_score numeric,
  p_recommendation text,
  p_setup_quality text,
  p_market_regime text,
  p_trend text,
  p_momentum text,
  p_sector text
) returns jsonb
language sql
security invoker
as $$
  select public.open_validated_paper_trade(
    auth.uid(),
    p_ticker,
    p_side,
    p_entry_price,
    p_stop_loss,
    p_target_1,
    p_target_2,
    p_quantity,
    p_confidence_score,
    p_recommendation,
    p_setup_quality,
    p_market_regime,
    p_trend,
    p_momentum,
    p_sector,
    'manual',
    null,
    1,
    now()
  );
$$;

create or replace function public.open_forward_validation_paper_trade(
  p_user_id uuid,
  p_signal_id uuid,
  p_ticker text,
  p_entry_price numeric,
  p_stop_loss numeric,
  p_target_1 numeric,
  p_target_2 numeric,
  p_quantity numeric,
  p_confidence_score numeric,
  p_recommendation text,
  p_market_regime text,
  p_sector text,
  p_signal_rank integer,
  p_risk_admitted_at timestamptz
) returns jsonb
language sql
security invoker
as $$
  select public.open_validated_paper_trade(
    p_user_id,
    p_ticker,
    'BUY',
    p_entry_price,
    p_stop_loss,
    p_target_1,
    p_target_2,
    p_quantity,
    p_confidence_score,
    p_recommendation,
    'Forward validation',
    p_market_regime,
    'Frozen swing trend',
    'Frozen pullback momentum',
    p_sector,
    'forward_validation',
    p_signal_id,
    p_signal_rank,
    p_risk_admitted_at
  );
$$;

create or replace function public.close_forward_validation_paper_trade(
  p_signal_id uuid,
  p_realized_r numeric,
  p_completed_at timestamptz
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  trade public.paper_trades;
  result public.paper_trades;
  pnl numeric;
begin
  if auth.uid() is null and auth.role() <> 'service_role' then
    raise exception 'Authentication required';
  end if;
  select * into trade
  from public.paper_trades
  where forward_validation_signal_id = p_signal_id and status = 'OPEN'
  for update;
  if not found then
    return '{}'::jsonb;
  end if;
  if auth.role() <> 'service_role' and auth.uid() <> trade.user_id then
    raise exception 'Paper account access denied';
  end if;
  pnl := p_realized_r * trade.initial_risk_amount;
  update public.paper_accounts
  set cash_balance = cash_balance + trade.entry_price * trade.quantity + pnl
  where user_id = trade.user_id;
  update public.paper_trades
  set
    status = 'CLOSED',
    realized_pnl = pnl,
    realized_rr = p_realized_r,
    remaining_risk_r = 0,
    remaining_fraction = 0,
    closed_at = p_completed_at
  where id = trade.id
  returning * into result;
  return to_jsonb(result);
end;
$$;

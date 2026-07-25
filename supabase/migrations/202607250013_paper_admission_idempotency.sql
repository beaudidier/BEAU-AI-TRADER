-- Make manual retries and cross-path paper admissions idempotent per ticker.

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
language plpgsql
security invoker
as $$
declare
  existing_trade public.paper_trades;
begin
  if auth.uid() is null then
    raise exception 'Authentication required';
  end if;
  perform pg_advisory_xact_lock(
    hashtextextended(auth.uid()::text || ':' || upper(p_ticker), 0)
  );
  select * into existing_trade
  from public.paper_trades
  where user_id = auth.uid()
    and ticker = upper(p_ticker)
    and status = 'OPEN'
  order by opened_at
  limit 1;
  if found then
    return to_jsonb(existing_trade);
  end if;
  return public.open_validated_paper_trade(
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
end;
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
language plpgsql
security invoker
as $$
declare
  existing_trade public.paper_trades;
  account public.paper_accounts;
  open_positions integer;
  open_risk_r numeric;
  daily_new_risk_r numeric;
  proposed_risk_r numeric;
  reset_at timestamptz;
  reason_text text;
begin
  if auth.uid() is null and auth.role() <> 'service_role' then
    raise exception 'Authentication required';
  end if;
  if auth.role() <> 'service_role' and auth.uid() <> p_user_id then
    raise exception 'Paper account access denied';
  end if;
  perform pg_advisory_xact_lock(
    hashtextextended(p_user_id::text || ':' || upper(p_ticker), 0)
  );
  select * into existing_trade
  from public.paper_trades
  where forward_validation_signal_id = p_signal_id
  limit 1;
  if found then
    return to_jsonb(existing_trade);
  end if;
  select * into existing_trade
  from public.paper_trades
  where user_id = p_user_id
    and ticker = upper(p_ticker)
    and status = 'OPEN'
  order by opened_at
  limit 1;
  if not found then
    return public.open_validated_paper_trade(
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
  end if;

  select * into account
  from public.paper_accounts
  where user_id = p_user_id;
  proposed_risk_r := greatest(
    0,
    (p_entry_price - p_stop_loss) * p_quantity
  ) / greatest(0.01, account.initial_balance * 0.01);
  select count(*), coalesce(sum(remaining_risk_r), 0)
  into open_positions, open_risk_r
  from public.paper_trades
  where user_id = p_user_id and status = 'OPEN';
  select coalesce(sum(initial_risk_r), 0)
  into daily_new_risk_r
  from public.paper_trades
  where user_id = p_user_id
    and timezone('America/New_York', risk_admitted_at)::date
      = timezone('America/New_York', p_risk_admitted_at)::date;
  reset_at := (
    date_trunc(
      'day',
      timezone('America/New_York', p_risk_admitted_at)
    ) + interval '1 day'
  ) at time zone 'America/New_York';
  reason_text := format(
    'An open %s paper position already exists.',
    upper(p_ticker)
  );

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
    p_signal_id::text,
    'paper_trade_automatic',
    upper(p_ticker),
    p_signal_id,
    reason_text,
    open_positions,
    open_risk_r,
    daily_new_risk_r,
    proposed_risk_r,
    p_signal_rank,
    upper(p_ticker),
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
    'limiting_positions', jsonb_build_array(
      jsonb_build_object(
        'id', existing_trade.id,
        'ticker', existing_trade.ticker,
        'remaining_risk_r', existing_trade.remaining_risk_r
      )
    )
  );
end;
$$;

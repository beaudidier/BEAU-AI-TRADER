-- Serialize retries for the same immutable forward-validation signal.

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
begin
  perform pg_advisory_xact_lock(hashtextextended(p_signal_id::text, 0));
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
end;
$$;

-- Disable short paper-trade execution until a short-specific plan engine is available.
create or replace function public.open_paper_trade(
  p_ticker text, p_side text, p_entry_price numeric, p_stop_loss numeric, p_target_1 numeric,
  p_target_2 numeric, p_quantity numeric, p_confidence_score numeric, p_recommendation text,
  p_setup_quality text, p_market_regime text, p_trend text, p_momentum text, p_sector text
) returns jsonb language plpgsql security invoker as $$
declare account public.paper_accounts; trade public.paper_trades; notional numeric;
begin
  if auth.uid() is null then raise exception 'Authentication required'; end if;
  if p_side <> 'BUY' or p_entry_price <= 0 or p_quantity <= 0 then raise exception 'Only validated long paper buys are supported'; end if;
  if p_stop_loss <= 0 or p_stop_loss >= p_entry_price or p_target_1 <= p_entry_price or p_target_2 <= p_target_1 then raise exception 'Invalid long paper-trade levels'; end if;
  insert into public.paper_accounts (user_id) values (auth.uid()) on conflict (user_id) do nothing;
  select * into account from public.paper_accounts where user_id = auth.uid() for update;
  notional := p_entry_price * p_quantity;
  if account.cash_balance < notional then raise exception 'Insufficient paper trading cash'; end if;
  update public.paper_accounts set cash_balance = cash_balance - notional where user_id = auth.uid();
  insert into public.paper_trades (user_id, ticker, side, entry_price, stop_loss, target_1, target_2, quantity, confidence_score, recommendation, setup_quality, market_regime, trend, momentum, sector)
  values (auth.uid(), upper(p_ticker), 'BUY', p_entry_price, p_stop_loss, p_target_1, p_target_2, p_quantity, p_confidence_score, p_recommendation, p_setup_quality, p_market_regime, p_trend, p_momentum, p_sector)
  returning * into trade;
  return to_jsonb(trade);
end;
$$;

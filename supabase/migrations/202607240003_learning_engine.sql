-- Learning fields are captured at paper-trade open and completed automatically on close.
alter table public.paper_trades add column if not exists setup_quality text not null default 'Watchlist';
alter table public.paper_trades add column if not exists market_regime text not null default 'Unknown';
alter table public.paper_trades add column if not exists trend text not null default 'Unknown';
alter table public.paper_trades add column if not exists momentum text not null default 'Unknown';
alter table public.paper_trades add column if not exists sector text not null default 'Unknown';
alter table public.paper_trades add column if not exists realized_rr numeric;
alter table public.paper_trades add column if not exists holding_minutes numeric;
alter table public.paper_trades add column if not exists mistakes jsonb not null default '[]'::jsonb;
alter table public.paper_trades add column if not exists learning_summary text;

drop function if exists public.open_paper_trade(text, text, numeric, numeric, numeric, numeric, numeric, numeric, text);
create function public.open_paper_trade(
  p_ticker text, p_side text, p_entry_price numeric, p_stop_loss numeric, p_target_1 numeric,
  p_target_2 numeric, p_quantity numeric, p_confidence_score numeric, p_recommendation text,
  p_setup_quality text, p_market_regime text, p_trend text, p_momentum text, p_sector text
) returns jsonb language plpgsql security invoker as $$
declare account public.paper_accounts; trade public.paper_trades; notional numeric;
begin
  if auth.uid() is null then raise exception 'Authentication required'; end if;
  if p_side not in ('BUY', 'SELL') or p_entry_price <= 0 or p_quantity <= 0 then raise exception 'Invalid paper trade'; end if;
  insert into public.paper_accounts (user_id) values (auth.uid()) on conflict (user_id) do nothing;
  select * into account from public.paper_accounts where user_id = auth.uid() for update;
  notional := p_entry_price * p_quantity;
  if p_side = 'BUY' and account.cash_balance < notional then raise exception 'Insufficient paper trading cash'; end if;
  update public.paper_accounts set cash_balance = cash_balance + case when p_side = 'BUY' then -notional else notional end where user_id = auth.uid();
  insert into public.paper_trades (user_id, ticker, side, entry_price, stop_loss, target_1, target_2, quantity, confidence_score, recommendation, setup_quality, market_regime, trend, momentum, sector)
  values (auth.uid(), upper(p_ticker), p_side, p_entry_price, p_stop_loss, p_target_1, p_target_2, p_quantity, p_confidence_score, p_recommendation, p_setup_quality, p_market_regime, p_trend, p_momentum, p_sector)
  returning * into trade;
  return to_jsonb(trade);
end;
$$;

create or replace function public.close_paper_trade(p_trade_id uuid, p_exit_price numeric)
returns jsonb language plpgsql security invoker as $$
declare account public.paper_accounts; trade public.paper_trades; pnl numeric; proceeds numeric;
begin
  if auth.uid() is null then raise exception 'Authentication required'; end if;
  if p_exit_price <= 0 then raise exception 'Invalid close price'; end if;
  select * into trade from public.paper_trades where id = p_trade_id and user_id = auth.uid() and status = 'OPEN' for update;
  if not found then raise exception 'Open paper trade not found'; end if;
  select * into account from public.paper_accounts where user_id = auth.uid() for update;
  pnl := (p_exit_price - trade.entry_price) * trade.quantity * case when trade.side = 'BUY' then 1 else -1 end;
  proceeds := p_exit_price * trade.quantity;
  update public.paper_accounts set cash_balance = cash_balance + case when trade.side = 'BUY' then proceeds else -proceeds end where user_id = auth.uid();
  update public.paper_trades set status = 'CLOSED', exit_price = p_exit_price, realized_pnl = pnl, realized_rr = case when abs(entry_price - stop_loss) * quantity > 0 then pnl / (abs(entry_price - stop_loss) * quantity) else 0 end, holding_minutes = greatest(0, extract(epoch from now() - opened_at) / 60), closed_at = now() where id = p_trade_id
  returning * into trade;
  return to_jsonb(trade);
end;
$$;

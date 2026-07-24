-- Paper trading accounts and user-owned simulated positions. No broker connectivity.
create table if not exists public.paper_accounts (
  user_id uuid primary key references auth.users(id) on delete cascade,
  initial_balance numeric not null default 10000 check (initial_balance > 0),
  cash_balance numeric not null default 10000,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.paper_trades (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  ticker text not null,
  side text not null check (side in ('BUY', 'SELL')),
  status text not null default 'OPEN' check (status in ('OPEN', 'CLOSED')),
  entry_price numeric not null check (entry_price > 0),
  exit_price numeric,
  stop_loss numeric not null check (stop_loss > 0),
  target_1 numeric not null check (target_1 > 0),
  target_2 numeric not null check (target_2 > 0),
  quantity numeric not null check (quantity > 0),
  confidence_score numeric not null check (confidence_score between 0 and 100),
  recommendation text not null,
  realized_pnl numeric,
  coach_analysis jsonb,
  opened_at timestamptz not null default now(),
  closed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists paper_trades_user_status_opened_idx on public.paper_trades (user_id, status, opened_at desc);
create trigger paper_accounts_updated_at before update on public.paper_accounts for each row execute procedure public.set_updated_at();
create trigger paper_trades_updated_at before update on public.paper_trades for each row execute procedure public.set_updated_at();

alter table public.paper_accounts enable row level security;
alter table public.paper_trades enable row level security;
create policy "paper accounts own records" on public.paper_accounts for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "paper trades own records" on public.paper_trades for all using (user_id = auth.uid()) with check (user_id = auth.uid());

create or replace function public.open_paper_trade(
  p_ticker text, p_side text, p_entry_price numeric, p_stop_loss numeric, p_target_1 numeric,
  p_target_2 numeric, p_quantity numeric, p_confidence_score numeric, p_recommendation text
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
  insert into public.paper_trades (user_id, ticker, side, entry_price, stop_loss, target_1, target_2, quantity, confidence_score, recommendation)
  values (auth.uid(), upper(p_ticker), p_side, p_entry_price, p_stop_loss, p_target_1, p_target_2, p_quantity, p_confidence_score, p_recommendation)
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
  update public.paper_trades set status = 'CLOSED', exit_price = p_exit_price, realized_pnl = pnl, closed_at = now() where id = p_trade_id
  returning * into trade;
  return to_jsonb(trade);
end;
$$;

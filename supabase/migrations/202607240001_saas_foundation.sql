-- SaaS foundation: profiles, subscriptions, private user data, RLS, and usage tracking.
create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  avatar_url text,
  timezone text default 'UTC',
  trading_experience text,
  risk_profile text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.subscriptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  plan text not null default 'FREE' check (plan in ('FREE', 'PRO', 'ELITE')),
  status text not null default 'active',
  trial_ends_at timestamptz,
  current_period_end timestamptz,
  stripe_customer_id text,
  stripe_subscription_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.watchlists (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.watchlist_items (
  id uuid primary key default gen_random_uuid(),
  watchlist_id uuid not null references public.watchlists(id) on delete cascade,
  ticker text not null,
  created_at timestamptz not null default now(),
  unique (watchlist_id, ticker)
);

create table if not exists public.saved_analyses (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  ticker text not null,
  analysis_json jsonb not null,
  created_at timestamptz not null default now()
);

create table if not exists public.backtest_runs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  ticker text not null,
  parameters jsonb not null,
  results jsonb not null,
  created_at timestamptz not null default now()
);

create table if not exists public.trades (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  ticker text not null,
  side text not null check (side in ('BUY', 'SELL')),
  entry_price numeric not null,
  stop_price numeric,
  target_price numeric,
  quantity numeric not null,
  status text not null default 'OPEN',
  opened_at timestamptz not null default now(),
  closed_at timestamptz,
  pnl numeric,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.user_settings (
  user_id uuid primary key references auth.users(id) on delete cascade,
  default_account_size numeric not null default 10000,
  default_risk_percent numeric not null default 1,
  preferred_currency text not null default 'USD',
  theme text not null default 'dark',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.usage_counters (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  metric text not null,
  period_start date not null,
  count integer not null default 0 check (count >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, metric, period_start)
);

create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, display_name) values (new.id, coalesce(new.raw_user_meta_data ->> 'display_name', '')) on conflict do nothing;
  insert into public.user_settings (user_id) values (new.id) on conflict do nothing;
  insert into public.subscriptions (user_id, plan, status) values (new.id, 'FREE', 'active') on conflict do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created after insert on auth.users for each row execute procedure public.handle_new_user();

create or replace function public.set_updated_at()
returns trigger language plpgsql as $$ begin new.updated_at = now(); return new; end; $$;

create trigger profiles_updated_at before update on public.profiles for each row execute procedure public.set_updated_at();
create trigger subscriptions_updated_at before update on public.subscriptions for each row execute procedure public.set_updated_at();
create trigger watchlists_updated_at before update on public.watchlists for each row execute procedure public.set_updated_at();
create trigger trades_updated_at before update on public.trades for each row execute procedure public.set_updated_at();
create trigger settings_updated_at before update on public.user_settings for each row execute procedure public.set_updated_at();
create trigger usage_updated_at before update on public.usage_counters for each row execute procedure public.set_updated_at();

alter table public.profiles enable row level security;
alter table public.subscriptions enable row level security;
alter table public.watchlists enable row level security;
alter table public.watchlist_items enable row level security;
alter table public.saved_analyses enable row level security;
alter table public.backtest_runs enable row level security;
alter table public.trades enable row level security;
alter table public.user_settings enable row level security;
alter table public.usage_counters enable row level security;

create policy "profiles own records" on public.profiles for all using (id = auth.uid()) with check (id = auth.uid());
create policy "subscriptions own records" on public.subscriptions for select using (user_id = auth.uid());
create policy "watchlists own records" on public.watchlists for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "watchlist items via owner" on public.watchlist_items for all using (exists (select 1 from public.watchlists w where w.id = watchlist_id and w.user_id = auth.uid())) with check (exists (select 1 from public.watchlists w where w.id = watchlist_id and w.user_id = auth.uid()));
create policy "saved analyses own records" on public.saved_analyses for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "backtests own records" on public.backtest_runs for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "trades own records" on public.trades for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "settings own records" on public.user_settings for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "usage own records" on public.usage_counters for select using (user_id = auth.uid());

-- Demo only (run manually in non-production): create users through Supabase Auth first; the trigger provisions their FREE records.

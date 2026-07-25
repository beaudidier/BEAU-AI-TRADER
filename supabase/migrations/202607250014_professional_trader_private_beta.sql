-- Invite-only professional-trader beta feedback, reviews, and monitoring.

create table if not exists public.private_beta_memberships (
  user_id uuid primary key references auth.users(id) on delete cascade,
  role text not null check (role in ('OWNER', 'ADMIN', 'TESTER')),
  active boolean not null default true,
  invited_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

insert into public.private_beta_memberships (user_id, role, active)
select id, 'OWNER', true
from auth.users
order by created_at
limit 1
on conflict (user_id) do nothing;

create or replace function public.is_private_beta_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.private_beta_memberships
    where user_id = auth.uid()
      and active
      and role in ('OWNER', 'ADMIN')
  );
$$;

create table if not exists public.beta_feedback (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  page text not null check (char_length(page) between 1 and 80),
  ticker text check (ticker is null or char_length(ticker) between 1 and 20),
  category text not null check (
    category in (
      'strategy logic',
      'entry/stop/target',
      'chart',
      'risk',
      'data quality',
      'usability',
      'bug',
      'missing context'
    )
  ),
  severity text not null check (severity in ('low', 'medium', 'high', 'critical')),
  message text not null check (char_length(message) between 10 and 5000),
  screenshot_reference text check (
    screenshot_reference is null
    or char_length(screenshot_reference) <= 500
  ),
  created_at timestamptz not null default now()
);

create table if not exists public.professional_signal_reviews (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  signal_id text,
  ticker text not null check (char_length(ticker) between 1 and 20),
  would_take_setup boolean not null,
  entry_logical boolean not null,
  stop_structurally_correct boolean not null,
  targets_realistic boolean not null,
  relevant_context_missing boolean not null,
  market_regime_makes_sense boolean not null,
  setup_confidence integer not null check (setup_confidence between 1 and 10),
  notes text check (notes is null or char_length(notes) <= 5000),
  created_at timestamptz not null default now()
);

create table if not exists public.beta_monitoring_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete set null,
  event_type text not null check (
    event_type in (
      'frontend_error',
      'backend_error',
      'failed_auth',
      'failed_market_data',
      'failed_paper_trade',
      'scheduler_failure'
    )
  ),
  severity text not null check (severity in ('warning', 'error', 'critical')),
  path text,
  method text,
  status_code integer,
  message text not null check (char_length(message) between 1 and 1000),
  context jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists beta_feedback_user_created_idx
  on public.beta_feedback (user_id, created_at desc);
create index if not exists professional_reviews_user_created_idx
  on public.professional_signal_reviews (user_id, created_at desc);
create index if not exists beta_monitoring_type_created_idx
  on public.beta_monitoring_events (event_type, created_at desc);

alter table public.private_beta_memberships enable row level security;
alter table public.beta_feedback enable row level security;
alter table public.professional_signal_reviews enable row level security;
alter table public.beta_monitoring_events enable row level security;

create policy "memberships visible to member or admin"
on public.private_beta_memberships for select
using (user_id = auth.uid() or public.is_private_beta_admin());

create policy "feedback insert own"
on public.beta_feedback for insert
with check (user_id = auth.uid());
create policy "feedback visible to owner or admin"
on public.beta_feedback for select
using (user_id = auth.uid() or public.is_private_beta_admin());

create policy "signal reviews insert own"
on public.professional_signal_reviews for insert
with check (user_id = auth.uid());
create policy "signal reviews visible to owner or admin"
on public.professional_signal_reviews for select
using (user_id = auth.uid() or public.is_private_beta_admin());

create policy "monitoring insert own"
on public.beta_monitoring_events for insert
with check (user_id = auth.uid());
create policy "monitoring visible to owner or admin"
on public.beta_monitoring_events for select
using (user_id = auth.uid() or public.is_private_beta_admin());

grant execute on function public.is_private_beta_admin() to authenticated;

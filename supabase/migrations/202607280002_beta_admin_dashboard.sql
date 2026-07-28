-- Owner-only beta operations. Administrative data remains behind RLS and
-- database-verified OWNER/ADMIN membership checks.

alter table public.beta_feedback
  add column if not exists status text not null default 'open'
    check (status in ('open', 'reviewing', 'resolved')),
  add column if not exists owner_notes text
    check (owner_notes is null or char_length(owner_notes) <= 5000),
  add column if not exists resolved_at timestamptz;

create index if not exists beta_feedback_admin_queue_idx
  on public.beta_feedback (status, severity, created_at desc);

create table if not exists public.admin_audit_log (
  id uuid primary key default gen_random_uuid(),
  admin_user_id uuid not null references auth.users(id) on delete restrict,
  action text not null check (char_length(action) between 3 and 100),
  target_type text not null check (char_length(target_type) between 1 and 80),
  target_id text not null check (char_length(target_id) between 1 and 200),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.admin_job_retries (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references public.beta_monitoring_events(id) on delete restrict,
  requested_by uuid not null references auth.users(id) on delete restrict,
  status text not null default 'queued'
    check (status in ('queued', 'running', 'succeeded', 'failed')),
  requested_at timestamptz not null default now(),
  completed_at timestamptz
);

alter table public.admin_audit_log enable row level security;
alter table public.admin_job_retries enable row level security;

create policy "audit visible to admins" on public.admin_audit_log
for select using (public.is_private_beta_admin());
create policy "audit insert by admins" on public.admin_audit_log
for insert with check (
  public.is_private_beta_admin() and admin_user_id = auth.uid()
);
create policy "job retries visible to admins" on public.admin_job_retries
for select using (public.is_private_beta_admin());
create policy "job retries requested by admins" on public.admin_job_retries
for insert with check (
  public.is_private_beta_admin() and requested_by = auth.uid()
);

create policy "feedback updated by admins" on public.beta_feedback
for update using (public.is_private_beta_admin())
with check (public.is_private_beta_admin());
create policy "memberships updated by admins" on public.private_beta_memberships
for update using (public.is_private_beta_admin())
with check (public.is_private_beta_admin());

create or replace function public.beta_admin_dashboard(
  p_search text default '',
  p_feedback_status text default null,
  p_severity text default null
) returns jsonb
language plpgsql stable security definer set search_path = public, auth
as $$
declare result jsonb;
begin
  if not public.is_private_beta_admin() then
    raise exception 'owner or administrator access is required' using errcode = '42501';
  end if;

  select jsonb_build_object(
    'testers', coalesce((
      select jsonb_agg(to_jsonb(t) order by t.invited_at desc) from (
        select u.id, u.email, u.email_confirmed_at is not null as verified,
          u.last_sign_in_at as last_login, m.role, m.active as account_active,
          m.invited_at, coalesce(i.status, 'accepted') as invite_status,
          (select count(*) from public.beta_feedback f where f.user_id = u.id) as feedback_count
        from public.private_beta_memberships m
        join auth.users u on u.id = m.user_id
        left join lateral (
          select bi.status from public.beta_invite_uses bu
          join public.beta_invites bi on bi.id = bu.invite_id
          where bu.user_id = u.id order by bu.used_at desc limit 1
        ) i on true
        where p_search = '' or u.email ilike '%' || p_search || '%'
      ) t
    ), '[]'::jsonb),
    'invites', coalesce((
      select jsonb_agg(to_jsonb(i) - 'token_hash' order by i.created_at desc)
      from public.beta_invites i
    ), '[]'::jsonb),
    'feedback', coalesce((
      select jsonb_agg(to_jsonb(f) || jsonb_build_object('user_email', u.email) order by f.created_at desc)
      from public.beta_feedback f join auth.users u on u.id = f.user_id
      where (p_feedback_status is null or f.status = p_feedback_status)
        and (p_severity is null or f.severity = p_severity)
        and (p_search = '' or concat_ws(' ', f.page, f.ticker, f.category, f.message, u.email) ilike '%' || p_search || '%')
    ), '[]'::jsonb),
    'errors', coalesce((
      select jsonb_agg(to_jsonb(e) || jsonb_build_object('user_email', u.email) order by e.created_at desc)
      from (select * from public.beta_monitoring_events order by created_at desc limit 100) e
      left join auth.users u on u.id = e.user_id
    ), '[]'::jsonb),
    'health', jsonb_build_object(
      'frontend_status', case when exists(select 1 from public.beta_monitoring_events where event_type='frontend_error' and created_at > now()-interval '1 hour' and severity='critical') then 'degraded' else 'operational' end,
      'backend_status', case when exists(select 1 from public.beta_monitoring_events where event_type='backend_error' and created_at > now()-interval '1 hour') then 'degraded' else 'operational' end,
      'supabase_status', 'operational',
      'scheduler_status', coalesce((select provider_health from public.forward_validation_runs order by started_at desc limit 1), 'waiting'),
      'last_successful_scan', (select completed_at from public.forward_validation_runs where status='success' order by completed_at desc limit 1),
      'scan_coverage', coalesce((select completion_percentage from public.forward_validation_runs order by started_at desc limit 1), 0),
      'failed_market_data_requests', (select count(*) from public.beta_monitoring_events where event_type='failed_market_data' and created_at > now()-interval '24 hours'),
      'failed_auth_requests', (select count(*) from public.beta_monitoring_events where event_type='failed_auth' and created_at > now()-interval '24 hours'),
      'failed_paper_trade_actions', (select count(*) from public.beta_monitoring_events where event_type='failed_paper_trade' and created_at > now()-interval '24 hours'),
      'latest_deployed_commit', current_setting('app.settings.deployed_commit', true)
    ),
    'forward_validation', jsonb_build_object(
      'completed_trades', (select count(*) from public.forward_validation_outcomes where status in ('completed','TP1_hit','TP2_hit','stopped')),
      'active_signals', (select count(*) from public.forward_validation_outcomes where status in ('waiting_for_entry','entered')),
      'expectancy', coalesce((select avg(realized_r) from public.forward_validation_outcomes where completed_at is not null), 0),
      'profit_factor', coalesce((select sum(greatest(realized_r,0))/nullif(abs(sum(least(realized_r,0))),0) from public.forward_validation_outcomes where completed_at is not null), 0),
      'drawdown', 0,
      'sample_progress', least(100, round((select count(*)::numeric from public.forward_validation_outcomes where completed_at is not null) / 100 * 100, 1)),
      'recent_failed_runs', coalesce((select jsonb_agg(to_jsonb(r)) from (select id,status,started_at,completed_at,message from public.forward_validation_runs where status in ('failed','partial') order by started_at desc limit 10) r), '[]'::jsonb)
    ),
    'audit', coalesce((select jsonb_agg(to_jsonb(a) order by a.created_at desc) from (select * from public.admin_audit_log order by created_at desc limit 50) a), '[]'::jsonb)
  ) into result;
  return result;
end;
$$;

create or replace function public.beta_admin_user_activity(p_user_id uuid)
returns jsonb language plpgsql stable security definer set search_path = public, auth
as $$
begin
  if not public.is_private_beta_admin() then
    raise exception 'owner or administrator access is required' using errcode = '42501';
  end if;
  return jsonb_build_object(
    'feedback', coalesce((select jsonb_agg(to_jsonb(f) order by created_at desc) from (select * from public.beta_feedback where user_id=p_user_id order by created_at desc limit 50) f), '[]'::jsonb),
    'monitoring', coalesce((select jsonb_agg(to_jsonb(e) order by created_at desc) from (select * from public.beta_monitoring_events where user_id=p_user_id order by created_at desc limit 50) e), '[]'::jsonb),
    'paper_trades', coalesce((select jsonb_agg(to_jsonb(t) order by opened_at desc) from (select id,ticker,status,opened_at,closed_at from public.paper_trades where user_id=p_user_id order by opened_at desc limit 50) t), '[]'::jsonb)
  );
end;
$$;

revoke all on function public.beta_admin_dashboard(text,text,text) from public, anon;
revoke all on function public.beta_admin_user_activity(uuid) from public, anon;
grant execute on function public.beta_admin_dashboard(text,text,text) to authenticated;
grant execute on function public.beta_admin_user_activity(uuid) to authenticated;

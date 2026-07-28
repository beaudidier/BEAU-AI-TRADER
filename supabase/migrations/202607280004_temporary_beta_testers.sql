-- Time-bound tester accounts and auditable owner/admin lifecycle actions.

alter table public.private_beta_memberships
  add column if not exists temporary boolean not null default false,
  add column if not exists expires_at timestamptz,
  add column if not exists expiry_extended_once boolean not null default false;

alter table public.private_beta_memberships
  drop constraint if exists temporary_beta_expiry_required;
alter table public.private_beta_memberships
  add constraint temporary_beta_expiry_required
  check (not temporary or expires_at is not null);

create table if not exists public.temporary_beta_account_audit (
  id uuid primary key default gen_random_uuid(),
  actor_user_id uuid not null references auth.users(id) on delete restrict,
  target_user_id uuid not null,
  action text not null check (
    action in ('created', 'password_rotated', 'expiry_extended', 'revoked', 'deleted')
  ),
  expires_at timestamptz,
  created_at timestamptz not null default now()
);

alter table public.temporary_beta_account_audit enable row level security;

create policy "temporary account audit visible to admins"
on public.temporary_beta_account_audit for select
using (public.is_private_beta_admin());

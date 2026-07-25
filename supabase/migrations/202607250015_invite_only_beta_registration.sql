-- Invite-only account registration. Clear invite tokens never reach storage.

create table if not exists public.beta_invites (
  id uuid primary key default gen_random_uuid(),
  token_hash text not null unique check (
    token_hash ~ '^[a-f0-9]{64}$'
  ),
  status text not null default 'active' check (
    status in ('active', 'used', 'revoked', 'expired')
  ),
  created_at timestamptz not null default now(),
  expires_at timestamptz not null check (expires_at > created_at),
  max_uses integer not null default 1 check (max_uses between 1 and 100),
  use_count integer not null default 0 check (
    use_count >= 0 and use_count <= max_uses
  ),
  created_by uuid not null references auth.users(id) on delete restrict,
  label text check (label is null or char_length(label) <= 120)
);

create table if not exists public.beta_invite_uses (
  id uuid primary key default gen_random_uuid(),
  invite_id uuid not null references public.beta_invites(id) on delete restrict,
  user_id uuid not null references auth.users(id) on delete cascade,
  used_at timestamptz not null default now(),
  unique (invite_id, user_id)
);

create index if not exists beta_invites_created_idx
  on public.beta_invites (created_at desc);
create index if not exists beta_invites_status_expiry_idx
  on public.beta_invites (status, expires_at);
create index if not exists beta_invite_uses_invite_idx
  on public.beta_invite_uses (invite_id, used_at desc);

alter table public.beta_invites enable row level security;
alter table public.beta_invite_uses enable row level security;

create policy "beta invites visible to admins"
on public.beta_invites for select
using (public.is_private_beta_admin());

create policy "beta invites created by admins"
on public.beta_invites for insert
with check (
  public.is_private_beta_admin()
  and created_by = auth.uid()
);

create policy "beta invites updated by admins"
on public.beta_invites for update
using (public.is_private_beta_admin())
with check (public.is_private_beta_admin());

create policy "beta invite uses visible to admins"
on public.beta_invite_uses for select
using (public.is_private_beta_admin());

create or replace function public.consume_beta_invite(
  p_token_hash text,
  p_user_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  selected_invite public.beta_invites%rowtype;
  next_use_count integer;
begin
  select *
  into selected_invite
  from public.beta_invites
  where token_hash = p_token_hash
  for update;

  if not found then
    return jsonb_build_object('ok', false, 'reason', 'invalid');
  end if;

  if selected_invite.status = 'revoked' then
    return jsonb_build_object('ok', false, 'reason', 'revoked');
  end if;

  if selected_invite.expires_at <= now()
    or selected_invite.status = 'expired' then
    update public.beta_invites
    set status = 'expired'
    where id = selected_invite.id
      and status <> 'revoked';
    return jsonb_build_object('ok', false, 'reason', 'expired');
  end if;

  if selected_invite.status = 'used'
    or selected_invite.use_count >= selected_invite.max_uses then
    update public.beta_invites
    set status = 'used'
    where id = selected_invite.id
      and status = 'active';
    return jsonb_build_object('ok', false, 'reason', 'exhausted');
  end if;

  next_use_count := selected_invite.use_count + 1;

  update public.beta_invites
  set
    use_count = next_use_count,
    status = case
      when next_use_count >= max_uses then 'used'
      else 'active'
    end
  where id = selected_invite.id;

  insert into public.beta_invite_uses (invite_id, user_id)
  values (selected_invite.id, p_user_id);

  insert into public.private_beta_memberships (user_id, role, active)
  values (p_user_id, 'TESTER', true)
  on conflict (user_id) do update
  set active = true;

  return jsonb_build_object(
    'ok', true,
    'invite_id', selected_invite.id,
    'remaining_uses', selected_invite.max_uses - next_use_count
  );
end;
$$;

revoke all on function public.consume_beta_invite(text, uuid) from public;
revoke all on function public.consume_beta_invite(text, uuid) from anon;
revoke all on function public.consume_beta_invite(text, uuid) from authenticated;
grant execute on function public.consume_beta_invite(text, uuid) to service_role;

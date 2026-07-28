-- Restore private-beta access for users who completed the invite flow before
-- their membership row was available. Invite evidence remains the authority.

insert into public.private_beta_memberships (user_id, role, active)
select distinct invite_use.user_id, 'TESTER', true
from public.beta_invite_uses as invite_use
on conflict (user_id) do update
set active = true;

insert into public.private_beta_memberships (user_id, role, active)
select invited_user.id, 'TESTER', true
from auth.users as invited_user
where invited_user.raw_user_meta_data ->> 'access' = 'private_beta_invite'
on conflict (user_id) do update
set active = true;

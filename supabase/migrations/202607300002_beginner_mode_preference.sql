alter table public.user_settings
  add column if not exists experience_mode text not null default 'advanced'
  check (experience_mode in ('beginner', 'advanced'));

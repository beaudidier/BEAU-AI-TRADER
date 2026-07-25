-- Presentation status and latest completed price for immutable validation setups.
alter table public.forward_validation_outcomes
  add column if not exists setup_status text not null default 'waiting_for_entry',
  add column if not exists current_price numeric,
  add column if not exists current_price_timestamp timestamptz,
  add column if not exists invalidation_reason text;

alter table public.forward_validation_outcomes
  drop constraint if exists forward_validation_outcomes_setup_status_check;

alter table public.forward_validation_outcomes
  add constraint forward_validation_outcomes_setup_status_check
  check (
    setup_status in (
      'waiting_for_entry',
      'entry_triggered',
      'expired',
      'invalidated',
      'completed'
    )
  );

update public.forward_validation_outcomes
set setup_status = case
  when status in ('entered', 'TP1_hit') then 'entry_triggered'
  when status = 'expired' then 'expired'
  when status = 'data_error' then 'invalidated'
  when status in ('TP2_hit', 'stopped', 'completed') then 'completed'
  else 'waiting_for_entry'
end;

-- ============================================================================
-- The booking page could not read its own settings.
--
-- Live, the very first call from the client page returned
--   42501 — permission denied for view public_settings
-- while the tables beside it read fine, so the page died before rendering
-- anything. The blanket `revoke all on all tables in schema public` in 0001
-- stripped the view; the grant that followed did not survive on the live
-- project, though it does locally.
--
-- Rather than depend on a table-level grant for this one object, serve it the
-- way everything else the public page touches is served: a security-definer
-- function. The view keeps its grant too, so existing references still work.
-- ============================================================================

grant usage  on schema public          to anon, authenticated;
grant select on public.public_settings to anon, authenticated;

create or replace function public.get_public_settings()
returns table (
  business_name    text,
  tagline          text,
  timezone         text,
  slot_step_min    integer,
  min_lead_hours   integer,
  max_advance_days integer,
  whatsapp_phone   text,
  accepting_bookings boolean,
  closed_message   text
)
language sql stable security definer
set search_path = public, pg_temp
as $$
  select s.business_name, s.tagline, s.timezone,
         s.slot_step_min, s.min_lead_hours, s.max_advance_days,
         s.whatsapp_phone, s.accepting_bookings, s.closed_message
  from public.settings s
  where s.id = 1;
$$;

-- driver_phone is deliberately absent above: the public page must never see it.

-- Postgres grants EXECUTE to PUBLIC on every new function, so revoking from
-- `anon` alone would be a no-op. Drop PUBLIC first, then name the roles.
revoke execute on function public.get_public_settings() from public;
grant  execute on function public.get_public_settings() to anon, authenticated;

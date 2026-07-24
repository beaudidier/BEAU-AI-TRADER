# SaaS Foundation

## Implementation plan

1. Add Supabase environment configuration, client helpers, and SQL migrations with RLS enabled for every user-owned table.
2. Add FastAPI access-token verification, token-scoped database access, rate-limit-ready middleware, user APIs, and plan entitlements.
3. Add React authentication context, protected/guest routes, and auth pages backed by Supabase Auth.
4. Add profile, preferences, billing, watchlist, saved-analysis, and saved-backtest interfaces while preserving market-data features.

## Supabase setup

1. Create a Supabase project and apply the SQL migration in `supabase/migrations/` through the Supabase CLI or SQL editor.
2. Enable Email and Google providers in **Authentication → Providers**. Set the site URL and redirect URLs for `/reset-password`.
3. Copy `backend/.env.example` to `backend/.env` and `frontend/.env.example` to `frontend/.env`; use the project URL and anon key in both. Keep service-role keys backend-only.
4. Run the seed SQL section in the migration only in a non-production project if demo data is wanted.

## Security model

- The browser never submits a trusted user ID. FastAPI derives the ID from a verified Supabase access token.
- Database calls use the caller's JWT, so RLS is the final authorization layer.
- Market-data endpoints remain public; all `/me/*` endpoints require a verified token.
- Billing limits are defined centrally in `backend/saas/entitlements.py` and counted in the billing-period usage table.

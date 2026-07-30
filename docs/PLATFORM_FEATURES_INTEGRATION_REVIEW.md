# Final Platform Features Integration Plan

Date: 2026-07-30

Review branch: `integration/platform-features-review`

Read-only base observed: `main` at `ea626a7f012f1d519cba1d2861d9c39dfe4931a3`

Scope: documentation-only assessment. No feature branch was merged, no migration was applied, no deployment occurred, and neither `main` nor `feature/day-trading-foundation` was changed.

## Final verdict

**NO-GO for direct product integration today. GO for a controlled integration rehearsal after the required revisions below.**

The preferred order remains correct:

1. `feature/portfolio-journal-workspace`
2. `feature/beginner-mode`
3. `feature/first-time-user-clarity`
4. `feature/beta-admin-dashboard`

All four features provide distinct value, so none supersedes another. However, none should be merged directly to `main` at its current tip. Portfolio and Beginner are based on older `main` (`d863e21`), their migration versions collide, and their shared frontend files conflict. First-Time User Clarity is product-review-ready in isolation, but it duplicates Beginner Mode state and rendering; after Beginner is integrated, its current tour mount can be bypassed. Beta Admin remains last because it adds the highest-risk privileged surface.

Use one isolated integration branch:

```text
integration/platform-features
```

Build and validate the combined result there. Do not use the documentation branch as the application integration branch.

## Exact branches and commits

| Order | Branch | Current commits to integrate, oldest first | Disposition |
|---:|---|---|---|
| 1 | `feature/portfolio-journal-workspace` | `da92208` (`feat: portfolio and journal workspace`), `b6b5808` (`test: verify portfolio journal ownership and csv safety`) | **MERGE AFTER REVISION** |
| 2 | `feature/beginner-mode` | `531ba71` (`feat: beginner trading mode`), `74b7734` (`test: verify beginner mode safety and usability flows`) | **MERGE AFTER REVISION** |
| 3 | `feature/first-time-user-clarity` | `c6a14a8` (`feat: first-time user clarity`), `5abb120` (`feat: guided first-login product tour`), `f9b7b4e` (`fix: guided tour preview issues`), `18d34c8` (`fix: final beginner tour clarity`) | **MERGE AFTER REVISION** |
| 4 | `feature/beta-admin-dashboard` | `a359f87` (`feat: beta admin dashboard`) | **MERGE AFTER REVISION** |

These SHAs identify the reviewed source states. If a feature branch receives the required revisions, record and review its new tip before integrating it; do not silently substitute a different commit.

### Branch disposition vocabulary

| Status | Branches in this plan |
|---|---|
| **MERGE** | None at the current tips |
| **MERGE AFTER REVISION** | Portfolio/Journal, Beginner Mode, First-Time User Clarity, Beta Admin Dashboard |
| **SUPERSEDED** | None |
| **KEEP RESEARCH-ONLY** | `research/day-trading-risk-guardrails`, `research/news-event-risk-engine` (outside this product merge train) |
| **REJECT** | None of the four product branches; direct as-is integration is rejected |

## Exact overlap and expected conflicts

Pairwise three-way simulations and exact branch path comparisons produced this matrix:

| Pair | Exact shared files | Expected result |
|---|---|---|
| Portfolio ↔ Beginner | `backend/saas/router.py`, `frontend/package.json`, `frontend/src/App.tsx`, `frontend/src/types/database.ts` | Manual resolution in `App.tsx` and `database.ts`; deliberate test-script resolution in `package.json`; review the clean textual combination in the backend router. |
| Portfolio ↔ First-Time Clarity | `frontend/package.json`, `frontend/src/App.tsx` | Manual `App.tsx` resolution; consolidate test scripts. |
| Portfolio ↔ Beta Admin | `frontend/src/App.tsx` | Manual route-list resolution. |
| Beginner ↔ First-Time Clarity | `frontend/package.json`, `frontend/src/App.tsx`, `frontend/src/pages/Dashboard.tsx` | Deterministic conflicts in `App.tsx` and `Dashboard.tsx`; semantic conflict in mode ownership and tour mounting. |
| Beginner ↔ Beta Admin | `frontend/src/App.tsx` | Manual provider/route resolution. |
| First-Time Clarity ↔ Beta Admin | `frontend/src/App.tsx` | Currently textually auto-mergeable pairwise, but manual review is still required after earlier resolutions. |

### Named shared areas

- `frontend/src/App.tsx`: touched by all four branches. It owns providers, protected routes, dashboard selection, journal routing, tour mounting, and admin routing. Resolve this file in integration order and test every retained route after each step.
- `frontend/src/types/database.ts`: Portfolio expands `PaperTrade`; Beginner expands `UserSettings`. The resolution must retain both complete models.
- `frontend/package.json`: Portfolio uses Node test runner under `test`; Beginner uses Vitest under `test` plus Playwright under `test:e2e`; First-Time Clarity uses Node under `test` plus `e2e`. Replace these collisions with explicit scripts such as `test:unit`, `test:contracts`, `test:tour`, and `test:e2e`, then make one aggregate `test`.
- `frontend/package-lock.json`: changed only by Beginner among the four feature branches, but it must be regenerated once after the final combined `package.json`. Do not hand-merge a stale lockfile.
- `backend/api.py`: changed only by Beta Admin among these four. Current `main` does not produce a textual conflict, but the router registration is security-sensitive and must be reviewed against the final app. Do not import any day-trading router or lifecycle code.
- Migrations: Portfolio and Beginner both use `202607280001`; Beta Admin uses `202607280002`. Current `main` already contains later `202607280003` and `202607280004`, so all three feature migration files must be renamed to new, unique versions.
- Routes: Portfolio adds `/journal/:tradeId`; Beta Admin adds `/admin`; Beginner changes the dashboard render path; First-Time mounts its tour in the dashboard path. Preserve every existing public/auth route and keep `/admin` authenticated plus server-authorized.
- Shared auth/profile components: First-Time changes `ProfileSettingsPage` and calls `useAuth` to namespace/reset tour progress. Beginner uses `AuthProvider` plus `ExperienceModeProvider` and persisted user settings. These must use the same authenticated user identity. No branch directly changes login components, but `App.tsx` provider ordering affects login/session transitions.

## Beginner Mode versus First-Time User Clarity

### Relationship

They overlap and currently conflict, but they are not functional duplicates as a whole:

- Beginner Mode supplies the authoritative persisted `experience_mode`, a dedicated beginner dashboard, safety gating, explanations, and a paper-trade review path.
- First-Time User Clarity supplies first-login onboarding, a 14-step guided tour, jargon explanations, setup presentation, help/restart controls, and reviewed copy.

The First-Time branch has passed local authenticated preview and real-user review. The tour was reduced to 14 steps, jargon explanations were added, and the first-login flow is considered understandable. Those findings make its isolated UX implementation merge-ready from a comprehension standpoint.

### Current semantic conflict

The branches contain two different mode systems:

- Beginner uses `ExperienceModeContext` backed by `user_settings.experience_mode`, defaulting existing users to `advanced`.
- First-Time uses `beau-display-mode` in `localStorage`, defaulting a user with no value to Beginner.

They also contain two beginner presentations:

- Beginner: `BeginnerDashboardPage` and `BeginnerPaperTradeReview`.
- First-Time: `BeginnerSetup` embedded conditionally in the existing `Dashboard`.

Most importantly, Beginner's `ProtectedApplication` returns `BeginnerDashboardPage` before rendering `Dashboard`, while First-Time mounts `ProductTour` only beside `Dashboard`. A naïve conflict resolution can therefore make the tour fail to start for Beginner users, which is a hard stop.

### Required resolution

- Beginner Mode remains the sole owner of mode state, default, persistence, and switching.
- Remove or adapt First-Time's `beau-display-mode` state and its duplicate mode button.
- Do not retain two independently calculated “best setup” beginner experiences. Reuse Beginner's existing safety/status/payload logic and apply First-Time's reviewed copy, tour targets, and jargon explanations to that UI.
- Mount `ProductTour` at the protected application shell or in both mode render paths so first authenticated login can start it regardless of current mode.
- Use the authenticated user ID for tour progress. Decide explicitly whether tour state remains per-browser local storage or becomes a server setting; test logout/login and two users on one browser.
- Preserve the 14 reviewed steps. Remap their DOM targets to the final combined Beginner/Advanced components and verify every target in both setup-present and setup-empty states.

### Integration decision

Integrate the branches **separately but consecutively on `integration/platform-features`**, Beginner first and First-Time second. Do not merge either directly to `main`, do not have one supersede the other, and do not pre-combine their histories into a replacement feature branch. The integration branch is the controlled place to reconcile them and produce an explicit resolution commit.

Beginner Mode should still be integrated because First-Time Clarity does not replace its server-persisted preference or safety workflow. First-Time Clarity is **not merge-ready in the four-branch combined state until the above reconciliation and combined tests pass**, despite being UX-review-ready in isolation.

## Branch-specific gates

### 1. Portfolio/Journal

**Private-beta risk:** Medium. It changes the core paper portfolio, adds persistent journal content and exports, and expands response data. Ownership failure would expose private notes.

**Pre-merge checks**

- Rebase or merge current `main` into the feature branch and review the resulting delta.
- Rename its migration to `202607300001_portfolio_journal_workspace.sql`.
- Run a real two-user Supabase RLS test for read and update isolation.
- Verify long/short P&L, R multiples, quote timestamps, zero stop distance, stale/missing quotes, and unchanged admission inputs.
- Verify CSV formula neutralization for `=`, `+`, `-`, `@`, tabs/newlines, quotes, commas, and Unicode.

**Manual conflict files:** `frontend/package.json`, `frontend/src/App.tsx`, `frontend/src/types/database.ts`; review `backend/saas/router.py`.

**Tests before merge:** existing six backend tests and four frontend contract tests; backend full suite; frontend lint/build; endpoint integration against a disposable Supabase schema; interactive journal and export tests.

**Smoke tests after merge:** portfolio loads; open/closed positions remain accurate; journal create/edit/refresh/direct link works; another user receives not-found/denied; exports open safely; existing paper open/close/admission remains unchanged.

**Rollback:** hide/remove journal navigation and unregister journal endpoints while preserving additive columns and user data. Revert portfolio response additions independently if needed. Never drop journal columns during emergency rollback.

### 2. Beginner Mode

**Private-beta risk:** Medium to high. It changes authenticated dashboard selection and introduces a provider/loading state for every session, while safety decisions shown in the client must remain subordinate to backend admission.

**Pre-merge checks**

- Rebase or merge the integration branch after Portfolio.
- Rename its migration to `202607300002_beginner_mode_preference.sql`.
- Resolve `PaperTrade` and `UserSettings` types without dropping Portfolio fields.
- Consolidate package scripts and regenerate the lockfile from the combined manifest.
- Verify settings RLS, two-user isolation, malformed/missing preference fallback, auth transition, and server rejection when client review appears allowed.

**Manual conflict files:** `backend/saas/router.py`, `frontend/package.json`, `frontend/package-lock.json`, `frontend/src/App.tsx`, `frontend/src/types/database.ts`.

**Tests before merge:** existing Vitest services tests and five Playwright flows; backend settings API tests; Portfolio regression suite; frontend lint/type-check/build; direct navigation through all protected routes in each mode.

**Smoke tests after merge:** existing users default to Advanced; mode persists per account; Beginner waiting/blocked/expired/stale/ready states work; only paper review is offered; Portfolio journal routes remain reachable; logout/login does not leak mode.

**Rollback:** force all users to Advanced and remove the provider/mode UI while retaining the additive database column and saved values. Re-enable only after the regression is fixed.

### 3. First-Time User Clarity

**Private-beta risk:** Medium after isolated review, high if combined incorrectly. The principal risks are tour non-start, tour state leaking between users, hidden targets, mode duplication, or overlay obstruction.

**Pre-merge checks**

- Start from the integration branch containing Portfolio and Beginner.
- Remove the duplicate localStorage mode authority and adapt `BeginnerSetup`/tour targets to Beginner's canonical UI.
- Mount the tour outside the branch that Beginner bypasses.
- Confirm all 14 reviewed steps, jargon explanations, setup-empty fallback, skip/resume/restart, focus trap, and 390px behavior.
- Repeat a real-user first-login review on the combined build, not only the isolated branch preview.

**Manual conflict files:** `frontend/package.json`, `frontend/src/App.tsx`, `frontend/src/pages/Dashboard.tsx`. Semantic/manual review is also required for `BeginnerSetup.tsx`, `ProductTour.tsx`, `ProfileSettingsPage.tsx`, `Sidebar.tsx`, `TradingChart.tsx`, `tour/productTour.js`, and setup-presentation files.

**Migration order:** No database migration. Its local tour storage must be versioned and user-namespaced.

**Tests before merge:** existing product-tour, setup-presentation, and guided-flow tests; all Beginner unit/E2E tests; fresh first login; completed second login; skip/resume/restart; two users in one browser; setup present/empty/stale/blocked; keyboard and screen reader; native iPhone Safari; combined lint/build.

**Smoke tests after merge:** tour starts exactly once for a new authenticated tester; all 14 steps find correct targets; close resumes; skip does not restart; profile restart works; switching modes does not lose or bypass the tour; journal/admin routes are not covered or blocked incorrectly.

**Rollback:** disable automatic tour start and remove the overlay mount while leaving clarity copy and non-invasive target attributes. Increment the tour version only for a deliberately re-reviewed replacement.

### 4. Beta Admin Dashboard

**Private-beta risk:** High. It adds privileged user activity, feedback, invite, account status, audit, monitoring, and retry operations. It must remain last.

**Pre-merge checks**

- Rebase or merge the fully tested integration branch into Beta Admin's context.
- Rename its migration to `202607300003_beta_admin_dashboard.sql`.
- Run an independent security review of every endpoint, RPC, policy, returned field, and audit action.
- Define OWNER versus ADMIN privileges, response allow-lists, retry idempotency, transactional mutation/audit behavior, and rate limits.
- Confirm `/admin` cannot be discovered as usable by MEMBER/inactive/unauthenticated users and that the backend always enforces authorization.

**Manual conflict files:** `frontend/src/App.tsx`; security review required for `backend/api.py`, `backend/saas/admin.py`, `frontend/src/services/adminApi.ts`, `AdminDashboardPage.tsx`, and the migration.

**Tests before merge:** live Supabase RLS/RPC role matrix; every endpoint for OWNER, ADMIN, MEMBER, inactive, and unauthenticated users; owner-disable protections; invite lifecycle; feedback updates; data minimization; audit failure/concurrency; retry allow-list/idempotency; frontend route/component/accessibility; all earlier feature regression suites.

**Smoke tests after merge:** admin overview works only for approved roles; member direct route/API/RPC access is denied; owner cannot self-disable; feedback/account/invite/retry actions audit correctly; tester login and all non-admin product behavior remain unchanged.

**Rollback:** hide/remove `/admin`, unregister the API router, revoke RPC execute grants if exposure is suspected, stop retry consumption, and use a forward migration to tighten/revert policies. Preserve audit records.

## Migration order

Current `main` already includes `202607280003_restore_private_beta_memberships.sql` and `202607280004_temporary_beta_testers.sql`. Do not introduce the features under their reviewed `202607280001`/`002` names because that creates duplicate versions and an out-of-order ledger.

Required new sequence:

1. `202607300001_portfolio_journal_workspace.sql`
2. `202607300002_beginner_mode_preference.sql`
3. `202607300003_beta_admin_dashboard.sql`

First-Time User Clarity has no migration. Before each application, compare local and remote Supabase migration ledgers. Apply only to a disposable integration environment until the entire train passes. A missing, duplicate, reordered, partially applied, or unexpectedly remote-only version is a hard stop.

## Exact integration procedure

### Branch and merge strategy

1. Confirm current `main` is clean and record its full SHA; do not modify it.
2. Create `integration/platform-features` from that exact `main` SHA in a new worktree.
3. Prefer `git merge --no-ff --no-commit <branch>` over cherry-picking. Each feature consists of a reviewed milestone and tests; preserving branch history makes provenance and rollback clearer.
4. Before each merge, update/revise the feature branch against the integration branch or perform the resolution in the isolated integration branch. Never resolve conflicts on `main`.
5. Commit each feature merge/resolution as its own milestone. Stop after each milestone for review; do not batch all four.

### Conflict resolution order

For Portfolio:

1. `backend/saas/router.py`
2. `frontend/src/types/database.ts`
3. `frontend/src/App.tsx`
4. `frontend/package.json`

For Beginner:

1. migration rename
2. `backend/saas/router.py`
3. `frontend/src/types/database.ts` (retain both `PaperTrade` and `UserSettings` additions)
4. `frontend/src/App.tsx` (retain journal route, add experience provider)
5. `frontend/package.json`
6. regenerate `frontend/package-lock.json`

For First-Time Clarity:

1. remove/rework duplicate mode state and `BeginnerSetup`
2. `frontend/src/pages/Dashboard.tsx`
3. `frontend/src/App.tsx` (mount tour across both mode paths)
4. `ProfileSettingsPage.tsx` plus auth/user-namespaced tour state
5. tour targets in Sidebar/chart/canonical Beginner UI
6. `frontend/package.json`, then regenerate lockfile

For Beta Admin:

1. migration rename and security review
2. `backend/api.py` router registration
3. `frontend/src/App.tsx` `/admin` route while retaining journal, providers, and tour
4. admin API/page plus server authorization

### Full test sequence

Run after every milestone:

1. `git diff --check`
2. verify changed-file scope and absence of day-trading/trading-logic files
3. clean frozen frontend dependency install
4. frontend lint
5. TypeScript build
6. relevant unit/contract tests
7. relevant Playwright/E2E tests
8. focused backend tests
9. full backend suite
10. disposable Supabase migration reset/upgrade and RLS tests
11. combined product smoke checklist

After all four:

1. run every Portfolio, Beginner, Tour/Clarity, and Admin test together
2. run full frontend and backend suites from clean environments
3. run fresh-schema and upgrade-schema migration paths
4. perform OWNER/ADMIN/MEMBER/inactive/unauthenticated role matrix
5. perform real-user first-login and 14-step tour review
6. perform paper-trade and journal two-user isolation checks
7. confirm no trading logic, day-trading foundation, collector, or live execution behavior changed

### Production verification sequence

This plan does not authorize deployment. If deployment is later approved:

1. create database backup/restore point and capture migration ledger
2. deploy migrations in the exact order above
3. deploy backend; verify health, auth, existing APIs, RLS, and admin denial before enabling UI
4. deploy frontend with admin visibility restricted and tour rollback control ready
5. test unauthenticated, existing Advanced tester, new first-time tester, MEMBER, ADMIN, and OWNER accounts
6. smoke paper trading, portfolio, journal isolation/export, mode persistence, 14-step tour, profile restart, and admin audit
7. monitor auth, frontend, paper-trade, Supabase, scheduler, and migration errors
8. stop rollout and execute the relevant rollback on any hard-stop condition

## Hard stop conditions

Stop integration or rollout immediately if any of the following occurs:

- Any trading strategy, scoring, entry, stop, target, position sizing, risk-admission, live execution, day-trading foundation, or collector logic changes.
- Authentication, session isolation, authorization, or RLS regresses.
- Any existing or new tester cannot log in, refresh a session, or log out normally.
- Paper trading open/close/admission, portfolio calculations, or existing risk limits fail.
- The 14-step tour does not auto-start exactly once for an eligible first-login user, cannot resume/restart, or is bypassed by Beginner Mode.
- `/admin`, admin data, or admin RPCs are usable by MEMBER, inactive, or unauthenticated users.
- Journal read/update isolation between users is broken.
- Local and remote migration ledgers mismatch, a version collides, or schema upgrade differs from fresh schema.
- A required build, lint, unit, integration, E2E, RLS, role-matrix, or production smoke test fails.
- The combined route tree loses or redirects an existing route unexpectedly.
- A generated lockfile contains unexplained dependency changes.

## Final go/no-go summary

| Question | Answer |
|---|---|
| Exact integration order | Portfolio/Journal → Beginner Mode → First-Time User Clarity → Beta Admin Dashboard |
| Portfolio merge-ready? | No; merge after migration rename, current-base refresh, conflict resolution, and real RLS tests. |
| Beginner Mode still required? | Yes. It is the canonical persisted/safety mode and is not superseded by First-Time Clarity. |
| First-Time User Clarity merge-ready? | UX-review-ready in isolation, including local preview, real-user review, 14 steps, jargon explanations, and understandable first login; **not merge-ready in the combined train** until duplicate mode state and tour mounting are reconciled with Beginner. |
| Should Beginner and First-Time be combined first? | Reconcile them consecutively on `integration/platform-features`; keep their histories separate and create an explicit integration-resolution commit. |
| Does either supersede the other? | No. Beginner owns mode/safety; First-Time owns onboarding/clarity. |
| Beta Admin last? | Yes, unconditionally, because it is the highest-risk privileged feature and depends on the final route/auth context. |
| Direct merge to `main` now? | **NO-GO.** |
| Controlled isolated integration after revisions? | **GO**, one milestone at a time, subject to all hard stops. |

## Review-branch validation

The update to `integration/platform-features-review` must contain only:

```text
docs/PLATFORM_FEATURES_INTEGRATION_REVIEW.md
```

Required validation:

```text
git diff --check
git diff --name-only HEAD^..HEAD
```

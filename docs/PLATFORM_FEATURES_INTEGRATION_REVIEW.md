# Platform Features Integration Review

Date: 2026-07-28

Assessment base: `main` at `d863e21`

Method: read-only branch diffs and three-way merge simulations. No branch was merged, no migration was applied, and no application code or deployment was changed.

## Executive decision

Do not merge any reviewed branch as-is.

The three product branches are valuable but require small integration revisions before they are eligible. The two research branches must remain research-only. In particular, `research/day-trading-risk-guardrails` is not a research-only delta: it includes a day-trading runtime, provider integrations, API and frontend routes, dependencies, acceptance artifacts, and automatic application startup/shutdown hooks. Directly merging it would touch the day-trading foundation and active collector, which is outside this review's permitted scope.

The recommended product integration sequence is:

1. Revise and merge `feature/portfolio-journal-workspace`.
2. Rebase, revise, and merge `feature/beginner-mode`.
3. Rebase, revise, and merge `feature/beta-admin-dashboard`.
4. Do not merge `research/day-trading-risk-guardrails`.
5. Do not merge `research/news-event-risk-engine`.

This order establishes the portfolio/journal API and richer `PaperTrade` model first, layers the experience-mode shell over the resulting routes and types second, and adds the privileged admin surface last, after the private-beta operational controls receive the strongest review.

## Cross-branch integration findings

### Shared files and likely merge conflicts

| File | Branches | Assessment |
|---|---|---|
| `frontend/src/App.tsx` | Beginner, Portfolio, Beta Admin, Day Trading | Deterministic textual conflicts in pairwise three-way simulations. It is a monolithic route/provider expression and must be reconciled manually after every earlier product merge. |
| `backend/saas/router.py` | Beginner, Portfolio | Both modify the file. The simulated merge did not show a conflict marker in the changed sections, but route/model proximity makes regression review necessary. |
| `frontend/package.json` | Beginner, Portfolio | Both add a `test` script with incompatible runners: Vitest versus Node's built-in test runner. Pairwise simulation reports overlapping modification. One canonical test command is required. |
| `frontend/src/types/database.ts` | Beginner, Portfolio | Deterministic conflict: Beginner adds `UserSettings.experience_mode`; Portfolio expands `PaperTrade`. The resolution must retain both. |
| `backend/api.py` | Beta Admin, Day Trading | Deterministic conflict if Day Trading were ever integrated: both register routers, and Day Trading also adds runtime lifecycle hooks. |

No reviewed files overlap with `research/news-event-risk-engine`; its coupling is conceptual rather than textual.

### Migration collision and ordering

`feature/beginner-mode` and `feature/portfolio-journal-workspace` both add migration version `202607280001`. Supabase migration versions must be unique; these cannot both land under their current names. `feature/beta-admin-dashboard` uses `202607280002`, so it also needs renumbering if Beginner takes `002`.

Use this final order:

1. `202607280001_portfolio_journal_workspace.sql`
2. `202607280002_beginner_mode_preference.sql` (rename from `202607280001_beginner_mode_preference.sql`)
3. `202607280003_beta_admin_dashboard.sql` (rename from `202607280002_beta_admin_dashboard.sql`)

Apply each migration only with its corresponding revised branch and verify the remote migration ledger before and after. All changes are additive, but `IF NOT EXISTS` does not make an incorrectly ordered or partially applied release safe.

### Duplicate components and responsibilities

- There are no exact duplicate React component filenames across the branches.
- `BeginnerPaperTradeReview`, the existing advanced paper-trading workflow, and Portfolio's `TradeReviewPage` duplicate parts of the paper-trade review responsibility. They should share one domain payload builder, status vocabulary, and journal/review link contract instead of evolving independently.
- Portfolio adds journal/review UI while Beta Admin adds per-user activity that exposes paper-trade summaries. Both need an agreed stable paper-trade representation.
- Every feature adds routing directly in `App.tsx`. This repeated route ownership is the main structural duplication and conflict source. Extract a route table or small route modules during integration, not by discarding any branch's routes.
- Beginner introduces Playwright/Vitest test infrastructure while Portfolio introduces Node test infrastructure without a lockfile update. Consolidate these into explicit `test:unit`, `test:integration`, and `test:e2e` scripts, with one aggregate `test`.

### Conflicting data models and inconsistent naming

- Beginner and Portfolio both redefine the same single-line `database.ts` declarations. The combined `UserSettings` must retain `experience_mode`, and the combined `PaperTrade` must retain Portfolio's journal, R-multiple, quote timestamp, and market-value fields.
- Portfolio uses both `realized_rr` and `unrealized_r`; main already uses several `_risk_r` fields. Pick either `*_r` or `*_rr` for API and frontend contracts and document whether each value is an R multiple.
- Portfolio calls its route `/journal/:tradeId` but its page `TradeReviewPage`, while Beginner calls its action “Review paper trade.” Adopt one user-facing concept and route naming scheme.
- Day Trading uses `/day-trading-lab`, `day_trading`, and `DAY_TRADING_LAB_ENABLED`. These are internally understandable but are not aligned with the research branch name `day-trading-risk-guardrails`; this reinforces that the branch combines multiple milestones.
- News Event Risk uses `artifact_manifest.json` while Day Trading uses `manifest.json`, and the two research packages use different directory suffixes and test-vector naming conventions. Normalize only if their contracts are later promoted into a common policy framework.

### Hidden coupling with `main`

- All five branches have `d863e21` as their merge base, so the assessment is against the current stated base rather than an older divergent foundation.
- Beginner depends on existing settings read/update behavior, authenticated Supabase session state, latest-signal evidence, portfolio risk admission, paper-trade opening, and main's default advanced experience.
- Portfolio depends on the existing `paper_trades` ownership RLS policy, quote payload timestamp conventions, paper-trading engine calculations, and main's paper-risk fields.
- Beta Admin depends on `private_beta_memberships`, `is_private_beta_admin()`, invites and invite uses, feedback, monitoring events, forward-validation runs/outcomes, paper trades, authenticated user-scoped Supabase clients, and a deployed-commit database setting.
- Day Trading attaches a background runtime to the main FastAPI process. That lifecycle coupling can start network/provider behavior merely by starting the API, even when the frontend feature flag hides the lab.
- News Event Risk has no runtime coupling today; its policy is not consumed by application code. Its hidden risk is the opposite: merging the documents could imply enforcement that does not exist.

## Branch assessments

### `feature/portfolio-journal-workspace` (`b6b5808`)

**User value:** High. It turns paper positions into a useful portfolio and learning journal, adds trade review, filters and exports, and exposes R-multiple and quote freshness context.

**Security risk:** Medium. The API correctly scopes reads and updates by both trade ID and authenticated user ID, rejects browser-supplied ownership/trading fields, bounds journal inputs, checks URL schemes, and retains RLS. Residual concerns are storing arbitrary remote screenshot URLs, formula-safe CSV behavior across all fields, data-retention/privacy expectations for journal content, and relying on an existing RLS policy without recreating or asserting it in the migration.

**Database changes:** Eleven additive columns on `paper_trades`; JSON tag arrays, confidence checks, review state, exit reason, URL, notes, lessons, and update timestamp. No destructive change.

**Overlaps/conflicts:** Overlaps Beginner in `backend/saas/router.py`, `frontend/package.json`, `frontend/src/App.tsx`, and `frontend/src/types/database.ts`. Deterministic conflicts occur in `App.tsx` and `database.ts`; package test scripts also need deliberate reconciliation. Its migration version collides with Beginner.

**Dependencies:** No new runtime package, but it changes the `test` script to Node's runner and does not update `package-lock.json`. That conflicts with Beginner's Vitest-based `test` command.

**Migration ordering:** Integrate first and retain version `202607280001`.

**API compatibility:** Additive GET `/paper-trading/{trade_id}` and PATCH `/paper-trading/{trade_id}/journal`; existing paper portfolio responses gain fields. Consumers should tolerate additive JSON. Verify route matching against existing `/paper-trading/open`, `/close`, and portfolio routes, and freeze a response schema.

**Frontend routing:** Adds `/journal/:tradeId`; manual reconciliation is required in `App.tsx`. Verify invalid IDs, direct navigation, browser back, and authorization failures.

**Private-beta behavior risk:** Medium. It changes the core Paper Trading page and portfolio calculations for all beta users, plus adds persistent user content and exports. It does not alter admission inputs, but calculation regressions could reduce trust.

**Tests present:** Six backend tests cover portfolio values, payload allow-listing, RLS/route scoping, cross-user isolation, ignored trading fields, and unsafe URL schemes. Four frontend source-inspection tests cover navigation, persistence/payload wiring, filters/exports/responsive markers, and CSV formula neutralization.

**Missing tests:** Real database RLS tests with two authenticated users; endpoint contract tests against Supabase; migration up/down or fresh/seeded database verification; React interaction tests; export round-trip tests with commas, quotes, Unicode, newlines, and all spreadsheet formula prefixes; missing/stale quote behavior; short-side R calculations; large journals/tag boundaries; URL privacy/CSP behavior; accessibility and mobile E2E.

**Decision:** **Revise**, then merge first.

**Rollback plan:** Disable journal/review navigation first; revert API/UI commits while leaving additive columns in place so user journal data is not destroyed. If response fields cause a regression, revert the engine response additions independently. Do not drop columns in an emergency rollback; export/back up user content and remove schema only in a later reviewed migration.

### `feature/beginner-mode` (`74b7734`)

**User value:** High. It provides a simpler, paper-only workflow, explains terminology, persists the experience choice, and blocks review for stale, invalid, expired, or risk-rejected setups.

**Security risk:** Low to medium. It does not enable live trading and defaults existing users to Advanced. The principal risk is client-side safety presentation drifting from authoritative backend admission rules. Client gating must never be treated as authorization or execution control.

**Database changes:** Adds non-null `user_settings.experience_mode` with `advanced` default and a two-value check.

**Overlaps/conflicts:** Conflicts with Portfolio in `App.tsx` and `database.ts`, overlaps its test script, and shares `backend/saas/router.py`. Conflicts with Beta Admin and Day Trading in `App.tsx`. Its migration version collides with Portfolio.

**Dependencies:** Adds pinned-range Playwright, PGlite, and Vitest dev dependencies plus a large lockfile update. Confirm Node version, CI/browser installation, lockfile reproducibility, and whether PGlite is necessary for retained tests.

**Migration ordering:** Integrate second; rename migration to `202607280002_beginner_mode_preference.sql`.

**API compatibility:** Adds optional `experience_mode` to the existing settings update model. Verify settings reads always return a valid value after migration and legacy/malformed values fall back safely. Paper-trade review still depends on existing trade-plan and portfolio APIs.

**Frontend routing:** It wraps the application with `ExperienceModeProvider` and replaces the normal dashboard content for Beginner users. The current logic only switches the dashboard fallback; direct protected routes remain advanced pages. Decide and test whether this is intentional. Preserve `/journal/:tradeId` from Portfolio during reconciliation.

**Private-beta behavior risk:** Medium to high. Although the database default is Advanced, the provider wraps all authenticated and guest routes, adds a loading interstitial, and changes dashboard selection. A preference read failure reports Advanced mode but should be tested to ensure it never strands the UI or leaks state between users.

**Tests present:** Unit tests cover migration/default behavior, preference load/save, safety statuses, stale data, setup selection, terminology, and payload construction. Five Playwright flows cover ready/paper-only behavior, keyboard use, 390px layout, safety copy, and preference persistence across refresh/session.

**Missing tests:** Backend settings endpoint integration and RLS; two-user preference isolation; unauthenticated/auth transitions; Supabase/network timeout and malformed preference recovery; direct navigation to every protected route in Beginner mode; conflict-resolution tests with Portfolio routes/types; authoritative server rejection despite client approval; loading/error accessibility; screen-reader semantics; browser matrix; database migration on populated settings rows.

**Decision:** **Revise**, then merge second.

**Rollback plan:** Keep the `experience_mode` column, force or default all users to Advanced, remove the provider/mode UI, and revert the optional settings field only if necessary. Never delete saved preferences during an operational rollback. Re-enable behind a beta cohort flag after fixes.

### `feature/beta-admin-dashboard` (`a359f87`)

**User value:** High for private-beta operations. It centralizes tester/invite state, feedback, errors, health, forward-validation status, audit history, account enablement, and constrained job retry requests.

**Security risk:** High. It introduces privileged reads and mutations over auth users, memberships, invites, feedback, monitoring, and job retries. Positive controls include database-backed active OWNER/ADMIN checks, RLS, security-definer functions with explicit authorization, revoked public/anon execution, owner-disable protections, audit records, and a retry allow-list. Required review areas include least-privilege grants, admin-versus-owner powers, sensitive fields returned by `to_jsonb`, search exposure, audit completeness/atomicity, rate limiting, CSRF assumptions for bearer tokens, account reactivation policy, and whether queuing a retry has an actual safe worker contract.

**Database changes:** Adds feedback workflow fields/index, `admin_audit_log`, `admin_job_retries`, RLS policies, membership/feedback admin update policies, and two security-definer RPCs.

**Overlaps/conflicts:** Deterministic `App.tsx` conflict with every UI-bearing reviewed branch. It also conflicts with Day Trading in `backend/api.py`. No direct dependency-file conflict.

**Dependencies:** No new package. It relies extensively on existing tables/functions and exact column/status names.

**Migration ordering:** Integrate third; rename to `202607280003_beta_admin_dashboard.sql` after the two feature migrations.

**API compatibility:** Adds `/admin/*` endpoints and a router; no intended public API break. Validate response schemas and errors rather than returning broad table rows. The API returns generic frontend errors, which is safe but may impede support diagnostics without correlation IDs.

**Frontend routing:** Adds protected `/admin`, but `ProtectedRoute` only proves authentication; authorization occurs after page load at the API. Add an admin-aware route/guard for UX while retaining server authorization. Preserve Portfolio and Beginner route/provider changes.

**Private-beta behavior risk:** High by design. Admins can disable accounts, alter feedback workflow, create/revoke invites, view user activity, and queue retries. A mistake affects access or beta operations. Merge only after a staging review with representative OWNER, ADMIN, MEMBER, inactive, and unauthenticated accounts.

**Tests present:** Backend tests cover authorization helper behavior, owner self-disable/owner protection, audit calls, retry allow-list behavior, and migration security markers.

**Missing tests:** Live Postgres/Supabase RLS and RPC privilege tests for every role; authorization tests for every endpoint; ADMIN-versus-OWNER policy tests; response data minimization; SQL wildcard/search edge cases; concurrency and transactionality of mutation plus audit; audit failure behavior; rate limits; idempotent retry requests; invite lifecycle integration; frontend component/route/accessibility tests; monitoring table absence/empty states; migration verification against production-like schema.

**Decision:** **Revise**, then merge third after security sign-off.

**Rollback plan:** Remove/hide the `/admin` frontend route and unregister the API router first. Revoke authenticated RPC execute grants if exposure is suspected. Preserve audit records. Stop the retry consumer before changing retry storage. Revert policies/functions in a reviewed forward migration; retain additive feedback fields/tables until data retention is resolved.

### `research/day-trading-risk-guardrails` (`864fa35`)

**User value:** Potentially high future value: live market-data plumbing, deterministic recording/replay, paper brokerage, health/acceptance tooling, a lab UI, and an extensive formal guardrail contract.

**Security risk:** Critical if merged as-is. It adds provider credentials/configuration, websocket/network behavior, a trading-like API surface, a paper broker, large runtime state, and automatic startup of `day_trading_runtime` with the FastAPI process. A frontend flag hides navigation but does not prevent backend startup or API exposure.

**Database changes:** None.

**Overlaps/conflicts:** Conflicts in `App.tsx` with all product branches; overlaps Beta Admin in `backend/api.py`; also changes shared dependency manifests, environment examples, configuration, sidebar, and `.gitignore`.

**Dependencies:** Adds exact pins for `certifi`, `httpx`, and `websockets` to both Python dependency manifests. Verify compatibility with Supabase/httpx transitive requirements and the repository's dependency-source policy before any future extraction.

**Migration ordering:** None, but runtime/config deployment order would be significant in a future dedicated milestone.

**API compatibility:** Adds a router and app lifecycle handlers. Startup behavior changes for every API process and is therefore not backward-neutral. Validate authentication, rate limits, tenancy, process multiplicity, state ownership, shutdown, degraded providers, and disabled-mode behavior before promotion.

**Frontend routing:** Adds `/day-trading-lab` and sidebar navigation gated by development or `VITE_DAY_TRADING_LAB_ENABLED`. Backend exposure is not equivalently gated.

**Private-beta behavior risk:** Critical. API startup may activate runtime behavior independent of UI visibility; artifacts and lab language may imply readiness; operational load and failure modes can affect the existing beta.

**Tests present:** Broad backend suites cover providers, API, data integrity, paper broker, recorder/replay, sessions, streams, multi-session acceptance, live summary, and session verification. Research contract and adversarial suites include generated vectors, mutation corpus, coverage, manifest, and validators.

**Missing tests:** Isolated-process and multi-worker ownership; real credential/tenant isolation; endpoint authentication/authorization; strict disabled-by-default backend gate; network outage/backpressure/reconnect storms; resource ceilings; observability and alerting; production dependency resolution; long-duration soak; kill/restart recovery; clock/DST/holiday behavior; full guardrail contract enforcement in every order path; proof that no live order endpoint/provider can be selected.

**Decision:** **Reject for direct integration; remain research-only.** If desired later, split the policy/docs/validators into a research-only branch and assess runtime, collector, broker, and UI as separate explicitly authorized milestones. Do not cherry-pick or merge it during the product sequence.

**Rollback plan:** Not applicable to this integration because it must not be merged. For any future controlled trial, gate backend registration and startup off by default, isolate the process, preserve recordings, revoke provider credentials, stop the runtime, unregister routes, and revert the deployment without touching the current collector.

### `research/news-event-risk-engine` (`a6cc771`)

**User value:** High as a specification and verification asset. It defines a future event-risk policy, schemas, vectors, traceability, known gaps, and adversarial validation.

**Security risk:** Low while research-only; high if represented as enforced protection when no runtime integration exists. Event/news sources and timing can be adversarial, stale, unavailable, or manipulated.

**Database changes:** None.

**Overlaps/conflicts:** No textual file overlap with the other reviewed branches and no likely merge conflict. Conceptually overlaps Day Trading's policy/guardrail layer and should eventually share policy versioning, reason-code, fail-closed, clock, and evidence conventions.

**Dependencies:** No application dependency changes. Research scripts use Python standard/application environment assumptions that should be pinned if promoted to CI.

**Migration ordering:** None.

**API compatibility:** No API changes and no application consumer. Any later API must define policy version, source provenance, freshness, timezone/session semantics, deterministic outputs, and fail-closed behavior.

**Frontend routing:** None.

**Private-beta behavior risk:** Low if it stays clearly labeled research; high reputational/safety risk if documentation is mistaken for active protection.

**Tests present:** Contract/schema tests, 2,177-line generated vector set, 287-line adversarial suite, mutation fixtures, manifest, traceability, and gap documentation.

**Missing tests:** Runtime adapter tests; provider/source outage and disagreement; manipulated headlines; embargo/revision/cancellation flows; timezone/DST and market-calendar boundaries; latency/freshness budgets; integration with order admission and Day Trading reason codes; signed/reproducible artifact generation in CI; performance and soak tests.

**Decision:** **Remain research-only.** Do not merge into the product integration sequence. Promotion requires a separate design review and implementation branch.

**Rollback plan:** Not applicable while unmerged. If research documents are ever published internally, revert the publication pointer rather than deleting evidence. If a future runtime adapter is deployed, disable event gating via a versioned, fail-closed rollout plan only after confirming what fallback behavior is safer; preserve decision logs for audit.

## Final integration plan

### 1. Exact merge order

Only after each branch is revised and rebased on the newly integrated `main`:

1. `feature/portfolio-journal-workspace`
2. `feature/beginner-mode`
3. `feature/beta-admin-dashboard`

Do not include either research branch in the merge train. Stop after each branch for review and production-like validation; do not batch the migrations.

### 2. Pre-merge checks

For every product branch:

- Rebase on current `main`; confirm the expected merge base and review `git diff main...branch`.
- Confirm the worktree is clean and the delta contains no secrets, generated credentials, live provider configuration, or unrelated collector/day-trading files.
- Run a no-commit merge simulation and record every conflict.
- Resolve routes in a readable route module/table while retaining all previously integrated protected routes and providers.
- Confirm dependency manifests and lockfiles agree; run a clean, frozen install.
- Run `git diff --check`, lint, type-check/build, focused tests, and the full relevant backend/frontend suites.
- Validate fresh database creation and upgrade from a production-like schema; inspect the Supabase migration ledger for unique, ordered versions.
- Review API schemas, authentication, authorization, RLS, data minimization, error behavior, rate limiting, and backward-compatible response fields.
- Add the missing tests identified in the branch assessment.

Branch-specific gates:

- Portfolio: real two-user RLS tests, formula-safe export matrix, stable portfolio response contract, and preserved risk calculations.
- Beginner: server-authoritative admission test, direct-route policy decision, multi-user preference isolation, and merged Portfolio route/type coverage.
- Beta Admin: independent security review, live RLS/RPC role matrix, audit transaction policy, idempotent retry semantics, response-field allow-lists, and staged OWNER/ADMIN/MEMBER exercises.

### 3. Post-merge checks

- Verify the resulting commit contains the intended branch only and no research/day-trading runtime files.
- Run `git diff --check` and confirm migration filenames are unique and ordered.
- Run backend lint/tests and frontend lint/unit/build/E2E from a clean install.
- Apply migrations to a disposable environment in order; compare schema and RLS policies with expectations.
- Exercise old clients or saved sessions against additive API changes.
- Confirm existing Advanced users retain the current dashboard and private-beta registration/invite behavior.
- Confirm monitoring shows no new authentication, paper-trade, frontend, or scheduler failures.
- Confirm rollback switches/routes are ready before exposure.

### 4. Smoke-test checklist

- [ ] Unauthenticated users are redirected from every protected route.
- [ ] Invite registration, login, logout, password reset, and session refresh still work.
- [ ] Existing users open in Advanced mode after the Beginner migration.
- [ ] Mode change persists per user; a second user cannot see the first user's preference.
- [ ] Beginner waiting, blocked, expired, stale, and ready states render correctly.
- [ ] Beginner can create only a paper-trade review and the backend can still reject unsafe admission.
- [ ] Advanced dashboard, scanner, workspace, learning, validation, evidence, feedback, and beta-guide routes still work.
- [ ] Paper portfolio values, long/short P&L, R multiples, and quote timestamps are correct.
- [ ] Journal direct link, save, refresh, validation, ownership, and not-found behavior work.
- [ ] CSV exports survive quotes/newlines/Unicode and neutralize spreadsheet formulas.
- [ ] MEMBER and inactive users receive 403 for every admin API and cannot read admin RPC data directly.
- [ ] OWNER and ADMIN behavior matches the approved role matrix.
- [ ] Owner self-disable and owner-target disable remain blocked.
- [ ] Feedback changes, account actions, activity views, invites, and retries produce complete audit records.
- [ ] Retry requests are allow-listed, idempotent, and do not directly perform destructive work.
- [ ] `/admin`, `/journal/:tradeId`, and all existing routes survive direct load, refresh, back, and unknown paths.
- [ ] No day-trading runtime starts, no collector changes, and no `/day-trading-lab` route/API is introduced.
- [ ] Private-beta banner, monitoring, runner status, forward validation, and paper-risk admission retain prior behavior.

### 5. Branches that must remain research-only

- `research/day-trading-risk-guardrails`: remain research-only and unmerged because its current branch also contains prohibited foundation/runtime/collector-adjacent integration. Split before any future assessment.
- `research/news-event-risk-engine`: remain research-only because it is a policy/verification package with no runtime enforcement or API integration.

## Validation of this review branch

The integration-review branch must contain only this documentation file relative to `main`. Required final checks are:

```text
git diff --check
git diff --name-only main...HEAD
```

The second command must report only `docs/PLATFORM_FEATURES_INTEGRATION_REVIEW.md`.

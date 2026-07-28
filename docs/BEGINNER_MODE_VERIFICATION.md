# Beginner Mode safety and usability verification

## Scope and verdict

This verification covers the presentation-only Beginner Mode on
`feature/beginner-mode`. It does not validate real-money trading, broker
execution, financial-advice suitability, profitability, or live readiness.
All trade levels and risk values remain outputs of the existing application
interfaces.

Result: **PASS** for the isolated paper-trading scenarios below.

## Traceability

| Scenario | Safety or usability rule | Expected result | Automated evidence |
|---|---|---|---|
| BM-E2E-001 | Entry has not triggered | Primary action is `Wait for entry`; disabled; no paper trade request | `waiting is fail-closed with the correct primary action` |
| BM-E2E-002 | Strategy blocked the setup | Primary action is `Setup blocked`; disabled | `blocked is fail-closed with the correct primary action` |
| BM-E2E-003 | Setup expired | Primary action is `Setup expired`; disabled | `expired is fail-closed with the correct primary action` |
| BM-E2E-004 | Data is stale | Fail closed with `Setup blocked` | `stale is fail-closed with the correct primary action` |
| BM-E2E-005 | Portfolio risk is exhausted | Fail closed and preserve the portfolio reason | `portfolio is fail-closed with the correct primary action` and unit portfolio-risk test |
| BM-E2E-006 | Entry triggered and all gates pass | One setup is shown; review exposes every risk field; confirmation calls only the paper endpoint | `ready flow exposes every risk field and opens only a paper trade` |
| BM-E2E-007 | Multiple candidates exist | Exactly one best eligible setup is rendered | Ready-flow E2E fixture contains two candidates; only `TEST` is rendered |
| BM-E2E-008 | No early-entry or real-money bypass | No `Buy now` or real-money button exists in any fail-closed state | Parameterized waiting/blocked/expired/stale/portfolio E2E tests |
| BM-E2E-009 | Plan values remain unchanged | Entry, stop, targets, quantity, maximum loss, confidence, recommendation, and risk/reward match the supplied plan | Paper payload unit test and ready-flow E2E assertions |
| BM-E2E-010 | First trade fits a normal desktop viewport | Review and confirmation actions are visible at 1440×900 without scrolling | Ready-flow bounding-box assertions |
| BM-E2E-011 | Mobile layout | No horizontal overflow at 390×844; setup and action remain readable | `390px mobile layout remains readable without horizontal overflow` |
| BM-E2E-012 | Keyboard accessibility | Named controls receive keyboard focus in order and expose visible focus styling | `keyboard-only flow has named controls, ordered focus, and visible focus styling` |
| BM-E2E-013 | Mode preference persistence | Advanced selection survives refresh and a new authenticated browser context | Mode preference E2E persistence test |
| BM-E2E-014 | Missing or invalid preference | Existing user safely sees unchanged Advanced Mode | Two compatibility E2E cases plus preference unit default test |
| BM-E2E-015 | Paper-only, non-promissory language | Paper-only warning and confidence disclaimer are visible; no guaranteed-profit or live-ready claim | Copy audit E2E test |
| BM-DB-001 | Migration applies without damaging existing rows | Existing row receives `advanced`; valid constraint is installed | PGlite isolated migration test |
| BM-DB-002 | Migration rollback is clean | Transaction rollback removes the column and preserves the pre-existing row | PGlite isolated migration test |

## Test environment

- Browser flow: the production React application in Vite with an isolated fake
  authenticated session and deterministic HTTP fixtures.
- Browser engine: locally installed headless Google Chrome through Playwright.
- Database: in-memory PGlite PostgreSQL. The migration runs inside a transaction
  and is rolled back before the database is closed.
- No shared Supabase project, private-beta environment, broker, market-data feed,
  or deployment is contacted.

## Commands and results

- `npm run test`: 11 tests passed, including the original 10 focused tests and
  the isolated migration test.
- `npm run test:e2e`: 12 browser scenarios passed.
- Relevant backend safety suite: 25 tests passed.
- `npm run build`: passed.
- `npm run lint`: passed.
- `git diff --check`: passed.

## Residual boundaries

- Responsive verification covers the required 390px mobile width and a
  1440×900 desktop viewport; it is not an exhaustive device certification.
- Browser tests use deterministic fixtures so safety states can be reproduced.
  They do not certify external data-provider availability.
- The preference migration remains unapplied outside the isolated test
  database.

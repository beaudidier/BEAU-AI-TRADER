# Portfolio Journal Security Verification

Scope: the existing authenticated paper portfolio and journal workspace on
`feature/portfolio-journal-workspace`. This verification adds no trading,
strategy, signal, scoring, entry, stop, target, broker, or risk-limit behavior.

| Scenario | Boundary | Expected outcome | Result | Evidence |
|---|---|---|---|---|
| PJ-SEC-01 | User A reads User B trade ID | Fail closed with not found | PASS | `test_two_users_cannot_read_or_update_each_others_journal` |
| PJ-SEC-02 | User A updates User B journal | No update; not found | PASS | `test_two_users_cannot_read_or_update_each_others_journal` |
| PJ-SEC-03 | Browser supplies `user_id` or plan fields | Ignored and absent from update | PASS | `test_client_user_id_and_trading_fields_are_ignored` |
| PJ-SEC-04 | Missing bearer token | 401 | PASS | `test_missing_token_is_rejected` |
| PJ-SEC-05 | Expired or malformed token | 401 | PASS | `test_invalid_or_expired_token_is_rejected` |
| PJ-SEC-06 | Revoked/deleted membership | Fail closed | PASS | `test_revoked_private_beta_member_is_rejected` |
| PJ-SEC-07 | Unsafe evidence URL | Rejected | PASS | `test_unsafe_reference_scheme_is_rejected` |
| PJ-CSV-01 | Commas, quotes, newlines and Unicode | RFC-style quoted field; quotes doubled | PASS | `CSV values are escaped and spreadsheet formulas are neutralized` |
| PJ-CSV-02 | Value begins `=`, `+`, `-`, or `@` | Leading apostrophe neutralizes formula | PASS | `CSV values are escaped and spreadsheet formulas are neutralized` |
| PJ-DATA-01 | Filtered view exported | Export receives the same filtered `rows` collection | PASS | frontend journal contract test |
| PJ-UI-01 | Mobile layout | Stacked cards and horizontally scrollable table | PASS | frontend journal contract test |
| PJ-UI-02 | Keyboard access | Native buttons, links, inputs and labelled filters | PASS | TypeScript build and source contract |

## Export matrix

| Export | Dataset | Filters/date semantics | Ownership | Formula-safe |
|---|---|---|---|---|
| Open positions | Filtered rows with `status=OPEN` | Inclusive ISO calendar-day boundaries | Authenticated portfolio response only | PASS |
| Closed positions | Filtered rows with `status=CLOSED` | Inclusive ISO calendar-day boundaries | Authenticated portfolio response only | PASS |
| Full journal | Same filtered rows visible in workspace | Inclusive ISO calendar-day boundaries | Authenticated portfolio response only | PASS |

Date filtering compares the stored UTC ISO date portion consistently for the
visible dataset and all exports. The API derives identity solely from the
verified bearer token and scopes paper-trade reads and updates by both trade ID
and authenticated user ID. Supabase RLS remains an independent owner boundary.

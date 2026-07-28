# Day-Trading Guardrail Adversarial Verification

Status: PASS

Scope: standalone research artifacts only

Network/external dependencies: none

Live execution: hard-disabled

This is a robustness test report, not a claim of legal or regulatory compliance,
live readiness, broker suitability, or trading performance.

## Result

- Canonical baseline: 62 rules and 221 vectors, PASS
- Existing unit tests: 10 PASS
- New adversarial tests: 6 PASS, including all 30 fixed mutations
- Malformed root payloads tested: empty, truncated object, array, null, boolean,
  string, and number; all rejected
- Seeded priority property cases: 475 shuffled samples plus duplicate-code case;
  deterministic
- Canonical policy and vector hashes: unchanged
- Overrides enabled by mutation: 0
- Future-live enablement by mutation: 0

## Mutation results

Every mutation below was expected to be rejected and was rejected.

| ID | Attacked invariant | Expected | Result |
|---|---|---|---|
| M001 | Contract manifest hash | Reject changed hash | PASS |
| M002 | Testvector manifest hash | Reject changed hash | PASS |
| M003 | Complete rule set | Reject removed rule | PASS |
| M004 | Unique rule/reason identifiers | Reject duplicate entry | PASS |
| M005 | Defined recovery action | Reject empty recovery | PASS |
| M006 | Unique contiguous priority | Reject duplicate priority | PASS |
| M007 | Non-negative limits | Reject negative ppm | PASS |
| M008 | Strict integer typing | Reject boolean-as-integer | PASS |
| M009 | Bounded integer representation | Reject value above signed 64-bit maximum | PASS |
| M010 | Canonical integer unit | Reject floating-percent unit | PASS |
| M011 | Future live hard-disabled | Reject enabled live state | PASS |
| M012 | Zero override authority | Reject allowed override | PASS |
| M013 | No override principal | Reject administrator authority | PASS |
| M014 | Unresolved future-live state | Reject dependency marked defined | PASS |
| M015 | Unresolved dependency evidence | Reject empty dependency set | PASS |
| M016 | Critical fail-closed field | Reject missing field | PASS |
| M017 | Closed policy schema | Reject unexpected root field | PASS |
| M018 | Non-empty rules | Reject empty rules array | PASS |
| M019 | Rule collection type | Reject null rules | PASS |
| M020 | Complete vector set | Reject removed vector | PASS |
| M021 | Unique vector identifiers | Reject duplicate vector | PASS |
| M022 | Expected-result integrity | Reject changed allow/block result | PASS |
| M023 | Critical vector input | Reject null observed value | PASS |
| M024 | Closed vector schema | Reject unexpected vector field | PASS |
| M025 | Non-empty vectors | Reject empty vector array | PASS |
| M026 | Stateful prerequisite ordering | Reject missing preceding state | PASS |
| M027 | Reconnect ordering | Reject reconnect-before-disconnect sequence | PASS |
| M028 | Worker fencing ordering | Reject stale epoch preceding ownership | PASS |
| M029 | Strict latency type/unit | Reject string-with-unit value | PASS |
| M030 | Policy root type | Reject null root | PASS |

The reproducible fixture definitions are stored in `mutation_corpus.json`. Tests use
seed `20260728`; no wall clock, random system seed, network call, external service,
database, or mutable shared state affects the result.

## Property and ordering verification

`test_priority_property_across_random_input_order` samples between 1 and 19 active
reason codes and shuffles every selection 25 times. Primary and ordered secondary
reasons remain identical because evaluation sorts by unique integer priority and
then reason code. Duplicate input reasons are deduplicated without changing the
result. Canonical JSON hashing sorts object keys, so root-object insertion order
does not alter bytes or hashes.

Policy array order remains part of the signed canonical artifact and a reordered
artifact is rejected. Evaluation order is nevertheless independent: decisions use
the explicit priority value rather than the array position.

## Stateful adversarial coverage

The fixed corpus mutates weekly-loss prerequisites, reconnect ordering, and
multi-worker fencing order. The canonical state vectors also cover daily and weekly
loss, drawdown, open risk, daily new risk, partial fills, stale state, reconnect,
restart persistence, kill-switch persistence, and worker conflicts. Removal,
repetition, stale ordering, or conflicting sequence changes alter the canonical
artifact and fail hash/canonical validation before evaluation.

## Minimal validator hardening

Adversarial work found and fixed validation sharp edges without changing the policy
or vector artifacts:

1. Root objects, exact root fields, non-empty rule/vector arrays, unexpected rule
   fields, unit names, signed-64-bit numeric bounds, fail-closed state, and
   unresolved dependency evidence now receive explicit checks.
2. Boolean values are explicitly rejected where JSON integers are required.
3. Malformed artifact exceptions, including missing-rule `StopIteration`, are
   converted to a deterministic `INVALID` CLI result instead of escaping as an
   uncaught traceback.

No policy threshold, reason priority, recovery action, canonical hash, or expected
decision changed.

## Reproduction

From the repository root:

```text
python3 research/day_trading_risk_guardrails/validate_contract.py
python3 -m unittest discover -s research/day_trading_risk_guardrails -p 'test_*.py' -v
python3 -m py_compile research/day_trading_risk_guardrails/*.py
git diff --check
```

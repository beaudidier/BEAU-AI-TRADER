# Adversarial verification

**Status:** deterministic research verification only
**Scope:** standalone policy artifacts and fixture-only evaluation
**Result:** PASS

The mutation catalog is committed in `mutation_fixtures.json`. Every mutation
uses fixed inputs and the Python standard library. No network, provider,
application, database, strategy, portfolio, broker, order, UI, or live-feed
integration is present.

## Results

| Mutation | Invariant attacked | Expected | Actual | Test |
|---|---|---|---|---|
| MUT-001 | Artifact integrity | Reject changed policy hash | PASS — rejected | `test_manifest_rejects_corrupted_artifact` |
| MUT-002–005 | Unique IDs and contiguous precedence | Reject duplicates, omissions, and gaps | PASS — rejected | `test_policy_identity_and_precedence_mutations` |
| MUT-006–012 | Closed schema and semantic completeness | Reject unsafe shape/action/audit/recovery mutations | PASS — rejected | `test_policy_shape_and_semantic_mutations`, `test_conflicting_recovery_is_rejected` |
| MUT-013–016 | Numeric units and bounds | Reject inverted, negative, excessive, and boolean values | PASS — rejected | `test_numeric_and_unit_boundary_mutations` |
| MUT-017–020 | Vector types and downward-only outputs | Reject null/empty/extra/unsafe values | PASS — rejected | `test_malformed_vector_types_and_ranges` |
| MUT-021–026 | UTC, causal time, revision time, supported range | Deterministic fail-closed result | PASS — blocked | `test_timestamp_mutations_fail_closed` |
| MUT-027 | Input/rule/object order | Byte-identical evaluation output | PASS — identical | `test_randomized_order_permutations_are_identical` |
| MUT-028 | Block precedence | Warning never lowers/cancels block | PASS — block retained | `test_duplicate_revision_conflict_mapping_permutations` |
| MUT-029 | Social isolation | No direction/confidence/size increase | PASS — rejected or downward-only | `test_mandatory_safety_rules_cannot_be_weakened` |
| MUT-030 | Future-live fail closed | Paper-only cannot be promoted | PASS — mutation rejected | `test_mandatory_safety_rules_cannot_be_weakened` |
| MUT-031–032 | Schema identity and requirements | Reject unknown or unsatisfied schema | PASS — rejected | `test_schema_mutations_are_rejected` |

## Invariant matrix

| Area | Immutable invariant | Evidence |
|---|---|---|
| Source trust | Unknown trust, unmapped identity, or invalid payload is fail-closed | MUT-021–026 plus canonical critical-input vectors |
| Precedence | Explicit priority wins independently of list/file/object order; warning cannot cancel block | MUT-002–005, MUT-027–028 |
| Revisions | Later or inverted revisions cannot rewrite an earlier point-in-time evaluation | MUT-023–025 and canonical revision vectors |
| Social safeguards | Social/X never creates/reverses direction or raises confidence/size | MUT-029 and mandatory NER-004–006 invariants |
| Future live | Required unresolved dependencies remain S4 paper-only | MUT-030 and mandatory NER-002 invariant |

## Validator leaks found and minimal fixes

Adversarial design review found these gaps before this report was marked PASS:

- top-level and condition objects were not fully closed to unexpected fields;
- condition-specific numeric bounds and inverted windows were not validated;
- required per-rule audit fields were not enforced;
- identical predicates could carry conflicting recovery/output definitions;
- source observation timestamps were parsed but not causally ordered;
- future observations and inverted revision timestamps were not fail-closed;
- critical safety rules could be structurally valid yet semantically weakened;
- generated artifacts did not have a committed integrity manifest.

The minimal fixes are confined to `contract.py`, generated fixtures, and the
artifact manifest. Canonical rule count, reason codes, severity choices, window
values, and expected decisions remain unchanged. Some scheduled test fixtures
now carry their correct point-in-time schedule-publication timestamps, and
revision fixtures carry the prior publication timestamp needed to prove causal
ordering.

This verification does not establish live readiness, compliance, provider
suitability, legal sufficiency, or predictive edge.

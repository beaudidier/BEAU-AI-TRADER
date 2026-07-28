# News and Event Risk Engine

**Status:** research specification only
**Scope:** a future, deterministic risk-control layer for news, earnings,
macro events, and social information
**Non-goals:** generating trades, predicting price direction, selecting a data
provider, estimating performance, or changing the day-trading foundation

## 1. Safety principles and evidence labels

The engine is a proposed safety layer between event data and a future trading
decision. It may restrict activity; it must never turn news sentiment, a
headline, or social activity into a `BUY` or `SELL` signal. An absence of known
events is not evidence that trading is safe.

This document uses three evidence labels:

- **Verified fact:** an externally checkable statement supported by a cited
  primary source.
- **Hypothesis:** a proposed policy or threshold that requires validation. It
  is not evidence of predictive edge.
- **Open question:** a product, data, legal, or risk decision that remains
  unresolved.

Core design constraints:

1. Fail closed when a high-consequence scheduled event is known but required
   timestamps or identity mappings are invalid.
2. Fail neutral, not directional, when unverified information arrives: warn,
   restrict, or ignore it; never infer a trade direction.
3. Keep source trust, event severity, and trade impact separate. A highly
   trusted source can carry an informational event, while an unverified report
   can justify caution because uncertainty itself is risky.
4. Use event-time data only as it was available at the decision timestamp.
5. Make every restriction deterministic, explainable, expiring, and
   reproducible from immutable inputs and versioned rules.
6. Treat all windows, thresholds, and mappings below as **hypotheses** until
   validated and approved.

## 2. Event taxonomy

Every normalized event has one primary category and may have secondary tags.
The category describes what happened, not whether price should rise or fall.

| Category | Included events | Default scope | Principal uncertainty |
|---|---|---|---|
| Earnings release | Scheduled or unscheduled results; preliminary results; restatements | Issuer, linked share classes | Schedule changes, revisions |
| Earnings call | Call start/end, prepared remarks, Q&A, transcript correction | Issuer | Live remarks may outrun transcripts |
| Guidance change | Initiation, raise, lower, withdrawal, qualitative outlook | Issuer and explicitly linked securities | Baseline and period comparability |
| SEC filing | 8-K, 10-Q, 10-K, registration, proxy, tender, bankruptcy, amendment | Filing entities and mapped securities | Form alone does not convey materiality |
| Insider transaction | Forms 3, 4, and 5; amendments | Issuer | Transaction codes, planned-sale context |
| Analyst action | Upgrade, downgrade, initiation, target or estimate change | Covered security | Entitlement, provenance, stale summaries |
| Merger or acquisition | Rumor, approach, agreement, termination, vote, regulatory decision | Parties and explicitly identified peers | Rumor status and deal conditions |
| Product announcement | Launch, delay, recall, safety notice, major contract or cancellation | Issuer | Commercial materiality |
| Legal or regulatory | Lawsuit, judgment, investigation, enforcement, approval, rejection, rule change | Named entities and affected market | Jurisdiction and appeal status |
| Management change | Appointment, departure, leave, succession, key-person event | Issuer | Interim versus permanent status |
| Dividend or buyback | Declaration, change, suspension, authorization, completion | Issuer | Ex-date versus announcement date |
| Fed decision | FOMC statement, projections, press conference, minutes, emergency action | Market-wide; rate-sensitive groups | Multiple release stages |
| CPI | Initial release, revision, correction, schedule change | Market-wide | Vintage and seasonal adjustment |
| PPI | Initial release, revision, correction, schedule change | Market-wide | Vintage and components |
| Jobs report | Employment Situation and material corrections/revisions | Market-wide | Multiple surveys and revisions |
| GDP | Advance, second, third estimates and comprehensive revisions | Market-wide | Vintage and estimate stage |
| Treasury event | Auctions, refunding, extraordinary measures, material schedule disruption | Market-wide; rate-sensitive groups | Which event is market-relevant |
| Geopolitical | Conflict, sanctions, elections, trade restrictions, state emergency | Explicitly exposed entities; possibly market-wide | Verification and exposure mapping |
| Breaking company news | Material event not yet classified above | Issuer | Speed, duplication, confirmation |
| CEO/company social post | Post by a verified official account or confirmed executive account | Issuer | Account control, deletion, ambiguity |
| X/social sentiment | Aggregate public discussion, velocity, coordination indicators | Observational only | Bots, sampling, manipulation, licences |

**Verified fact:** EDGAR is the SEC's primary filing channel, and Forms 3, 4,
and 5 are among the forms submitted through it. SEC insider datasets reproduce
the structured filings as filed and warn that submissions can contain
inconsistencies or discrepancies. Therefore, filing provenance is authoritative
for what was filed, but parsed content still requires validation
([SEC filing overview](https://www.sec.gov/submit-filings),
[SEC insider data documentation](https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets)).

**Open questions:** Which forms, jurisdictions, instruments, asset classes, and
issuer relationships are in initial scope? How are ETFs, ADRs, options, dual
listings, subsidiaries, suppliers, and acquisition targets mapped without
creating speculative contagion?

## 3. Source hierarchy

Trust is assigned to the specific item and retrieval path, not permanently to a
brand. A copied headline does not inherit the original publisher's trust.

| Trust level | Sources | Permitted use |
|---|---|---|
| T1 — authoritative primary | Official filings and filing amendments; exchange notices; government/statistical releases and corrections | Establish that the source published the item; eligible for all severities after schema, signature/domain, identity, and timestamp checks |
| T2 — attributable primary | Company investor-relations releases, issuer regulatory newsroom, official webcast, authenticated company/executive account | Establish issuer-attributed statements; eligible for high risk or trade block when identity is verified and the rule applies |
| T3 — high-quality secondary | Major newswires with direct attribution; licensed established financial media | Corroboration and breaking-news controls; may cause temporary restrictions, but disputed high-consequence claims require primary confirmation or two independent reliable reports |
| T4 — specialist/entitled | Authenticated analyst reports and established specialist publications | Warning or confidence reduction; never treated as an official fact unless the primary material is obtained |
| T5 — identified social | Known journalists, analysts, executives, employees, or observers on social media | Lead generation and warnings only unless the account and underlying primary statement are independently verified |
| T6 — unverified | Anonymous posts, screenshots, forwarded messages, unattributed summaries, sentiment aggregates | Ignore for facts and direction; optionally record manipulation/operational-risk indicators |

Trust controls factual status, not predicted market effect. “Verified account”
badges alone must not establish identity. Independence is absent when two
stories trace to the same source, press release, screenshot, or syndication
feed.

**Hypothesis:** T1/T2 items may activate deterministic issuer or market
restrictions immediately. T3 reports may activate a short precautionary
restriction for a potentially catastrophic event while corroboration is sought.
T4/T5 may lower confidence or set caution only. T6 cannot affect position
direction, size, or stops; it may only create an internal integrity alert.

**Open questions:** Which feeds qualify at each level? What authentication,
latency, correction, and uptime evidence is required? No provider is recommended
by this document.

## 4. Time, freshness, revisions, and conflicts

### Required clocks

Store all timestamps in UTC with source timezone and original text retained:

- `event_at`: when the event occurred or is scheduled to occur.
- `published_at`: publisher-declared first-publication time.
- `first_seen_at`: first observation by the ingestion boundary.
- `ingested_at`: durable receipt time in the engine.
- `updated_at`: publisher-declared update time, if any.
- `supersedes_event_id`: prior item replaced or corrected by this item.

Never substitute ingestion time for publication time. Preserve uncertainty with
precision (`exact`, `minute`, `date_only`, `range`, `unknown`) and a
`timestamp_confidence` value. The decision clock uses the earliest defensible
availability time: no earlier than both `published_at` and `first_seen_at`.

### Candidate stale-news policy

**Hypothesis:** freshness is category-specific and evaluated at decision time:

| Item | Candidate treatment |
|---|---|
| Unscheduled breaking item | New for 30 minutes; active while its rule remains unresolved; stale for initiating a new warning after 24 hours unless materially updated |
| Scheduled macro release | Match the exact release instance/vintage; the release shock window expires per Section 8, while revisions remain separately auditable |
| Earnings release/call | Active through the earnings windows in Section 7; do not roll an old quarter into a new one |
| Filing or company release | Active until its category rule expires or it is superseded; never infer freshness from a republished story |
| Social item | Eligible for verification for 15 minutes; otherwise ignore as a factual input; retain only if permitted |

These are safety-policy candidates, not performance estimates. Validation may
support longer, shorter, or category-specific values.

### Revisions, duplicates, and conflicts

1. Fingerprint canonical URL, source-native ID, normalized headline/body hash,
   issuer, event category, and event time.
2. Cluster syndications but retain every source record and receipt timestamp.
   Duplicate count is not independent confirmation and must not increase
   severity or sentiment weight.
3. Append corrections and revisions as new immutable versions linked by
   `supersedes_event_id`; never overwrite the originally seen value.
4. Re-evaluate only decisions after the revision became available. Never
   retrofit revised data into earlier decisions.
5. On conflicts, preserve each claim, its provenance, and a
   `conflict_group_id`. Prefer a later explicit correction from the same
   primary source for current state, without erasing history.
6. If high-consequence reports conflict and cannot be resolved, classify the
   claim as disputed and choose the more restrictive non-directional control.
   A conflict must never be averaged into a synthetic “fact.”

**Verified fact:** BLS warns that archived CPI and Employment Situation releases
may have been revised, maintains errata, and can revise scheduled release dates.
This supports explicit data vintages and schedule updates rather than assuming
the first calendar or value is final
([BLS CPI archive](https://www.bls.gov/bls/news-release/cpi.htm),
[BLS Employment Situation archive](https://www.bls.gov/bls/news-release/empsit.htm),
[BLS errata](https://www.bls.gov/errata/),
[BLS revised release dates](https://www.bls.gov/bls/2025-lapse-revised-release-dates.htm)).

## 5. Severity model

Severity measures required restraint, not bullishness or bearishness.

| Level | Meaning | Candidate control | Exit condition |
|---|---|---|---|
| S0 — informational | Verified event with no applicable risk restriction | Display and audit only | Record expiry |
| S1 — caution | Uncertainty or elevated but bounded event risk | Warning; confidence reduction may apply | Rule expiry or resolution |
| S2 — high risk | Material volatility, gap, liquidity, or verification risk | Size/risk restrictions; no risk expansion | Cooldown plus data-health checks |
| S3 — trade block | New exposure is unsafe under a deterministic rule | Block new/added exposure in scope; allow only pre-approved risk-reducing actions | Explicit expiry and rule re-evaluation |
| S4 — emergency halt | Market-wide or system-wide event/data integrity failure | Paper-only mode or halt automated order initiation; preserve operator controls | Authorized release after health and event checks |

Severity is the maximum of applicable rules, with scope unioned across affected
instruments. It must not silently decay: expiry is explicit, and extensions
create audit records. A severity reduction requires current source health,
resolved timestamps, and a rule outcome; a positive headline does not cancel a
block.

**Hypothesis:** risk-reducing actions during S3/S4 should be defined narrowly
and tested separately so a “block” cannot trap a position. Whether automated
flattening is ever allowed is an **open question** outside this research scope.

## 6. Trade-impact decision table

The layer returns constraints to a future decision system; it does not return
trade direction.

| Condition | Impact |
|---|---|
| Scheduled event inside a configured blackout window | Block new exposure and additions for affected scope |
| Unscheduled material T1/T2 event with unresolved market response | Trade block, or paper-only if market-wide |
| Potentially catastrophic T3 breaking report awaiting confirmation | Time-limited precautionary trade block; no directional inference |
| T4/T5 item without primary confirmation | Caution or confidence reduction only; never a new signal |
| T6/anonymous claim or sentiment aggregate | Ignore as fact and trade input; optional integrity warning |
| Valid informational event outside an active window | Informational only |
| Multiple independent verified events | Apply each rule; do not add pseudo-confidence merely because headlines are numerous |
| Missing/invalid critical calendar, clock, symbol mapping, or source health | Trade block for affected scope; paper-only if scope cannot be bounded safely |

Candidate impact semantics:

- **Blocks a trade:** prevents opening or increasing exposure; never transforms
  one direction into the other.
- **Reduces confidence:** caps an upstream confidence value. It cannot promote a
  rejected decision or manufacture a signal.
- **Changes position size:** applies a downward-only multiplier to the smaller
  of upstream and portfolio limits. Candidate S1 cap: `0.75`; S2 cap: `0.50`;
  S3/S4: `0` for new risk. These are validation hypotheses.
- **Tightens risk:** forbids widening stops or increasing total risk. Automatic
  stop tightening can itself increase execution risk and is an **open question**;
  the safe default is a risk-budget cap, not forced price-level movement.
- **Paper-only mode:** records hypothetical decisions and prohibits automated
  live order initiation.
- **Informational only:** displayed and logged with no numerical influence.

News sentiment alone must never create, reverse, or confirm a `BUY`/`SELL`
signal. Sentiment may not lift confidence, increase size, loosen risk, cancel a
block, or establish a fact.

## 7. Earnings rules

All windows are **hypotheses** and use the latest verified schedule. “Before”
and “after” refer to the scheduled or actual event time, not the trading
session date.

1. **Schedule uncertainty:** if the earnings date is unconfirmed or conflicting
   within seven calendar days of the earliest candidate date, set S1. If the
   exact time (before open/after close) is unknown on the event date, set S3 for
   new issuer exposure for the entire session.
2. **Pre-earnings blackout:** from 30 minutes before the regular-session close
   on the last session preceding an after-close/before-open release until the
   post-release cooldown ends, set S3 for new issuer exposure.
3. **Intraday release:** set S3 from 60 minutes before the verified release
   through at least 60 minutes after publication.
4. **Pre-earnings risk:** from five trading sessions before the release until
   the blackout, set S1; cap new size at 75% and forbid risk expansion.
5. **Post-earnings volatility:** set S2 from publication through the later of
   the next regular-session open plus 60 minutes or completion of the earnings
   call plus 30 minutes. Missing, halted, or abnormal market data extends S3.
6. **Guidance surprise:** do not label “surprise” without a versioned,
   comparable baseline and period/currency/unit match. A verified guidance
   initiation, withdrawal, or material change sets at least S2 regardless of
   direction. Ambiguous comparisons are “unknown,” not positive or negative.
7. **Conference-call risk:** set S3 for new exposure from 15 minutes before call
   start through call end; set S2 for 30 minutes after. If no reliable end time
   exists, use the published maximum duration plus a bounded fallback and flag
   uncertainty.
8. **Overnight positions:** candidate default is no new position intended to
   remain overnight across a confirmed earnings release. Existing exposure is
   not automatically liquidated by this layer; handling requires a separately
   approved portfolio policy. Exceptions are an **open question**, not implied
   permission.

Rescheduled, cancelled, delayed, preliminary, or leaked results create a new
event version and immediate re-evaluation. A leak is not treated as the official
release without verification.

## 8. Macro and Treasury rules

Use official calendars, monitor changes, and store the calendar version used by
each decision. A date-only schedule is insufficient for live automation.

**Verified facts:** BLS publishes release schedules with times and updates its
calendar. FOMC materials can be released in stages: for example, an official
meeting page records a statement and projections at 2:00 p.m. ET and minutes on
a later date. These facts justify distinct event instances rather than one
generic “Fed day”
([BLS release schedule](https://www.bls.gov/schedule/2026/home.htm),
[Federal Reserve meeting materials](https://www.federalreserve.gov/monetarypolicy/fomcpresconf20260617.htm)).

Candidate market-wide windows:

| Event | Before | After | Candidate severity |
|---|---:|---:|---|
| FOMC decision/projections | 30 min | 60 min | S3; S2 through press-conference end + 30 min |
| FOMC press conference | 15 min | 30 min | S3 during conference; S2 after |
| Emergency Fed action | Immediate | Until authorized review | S4 |
| CPI / PPI | 15 min | 30 min | S3, then S2 until 60 min if market data are unstable |
| Jobs report | 15 min | 30 min | S3, then S2 until 60 min if market data are unstable |
| GDP | 15 min | 30 min | S3, then S1 until 60 min |
| Material Treasury auction/refunding event | 10 min | 15 min | S2; escalate on data/market instability |

Rules:

1. Block new market-wide exposure during S3; existing positions are governed by
   a separate portfolio policy.
2. Extend S3 when the release is late, embargo status is unclear, official
   endpoints disagree, the clock is unhealthy, or quotes/trades are stale.
3. Do not compare actual versus consensus unless the consensus snapshot,
   contributor policy, timestamp, units, and vintage are licensed and stored.
   Even then, the comparison may only adjust risk downward.
4. Treat initial and revised CPI, PPI, jobs, and GDP values as distinct vintages.
5. Apply a market-wide S4 paper-only halt when an emergency central-bank action,
   exchange-wide halt, major market-data failure, or verified systemic event
   prevents safe scoping. Geopolitical headlines alone do not automatically
   create S4; identity, scope, and market-function evidence are required unless
   infrastructure integrity is unknown.
6. A schedule outage inside 24 hours of a known high-impact release is S2; if
   the exact time cannot be validated by the start of its potential window, it
   becomes S3.

**Open questions:** Which Treasury auctions and maturities qualify, what
market-wide instrument universe is covered, whether early closes change
windows, and which observable market-health criteria release an extended halt?

## 9. X and social-information rules

Social information is adversarial and lossy by default.

Risks include bot amplification, compromised accounts, impersonation,
look-alike handles, deleted or edited posts, screenshots without provenance,
quote-context loss, mistranslation, coordinated pumping, selective sampling,
API coverage gaps, and engagement metrics that are neither independent nor
stable.

Required controls:

1. Verify account identity against a versioned allowlist plus an independent
   official domain or filing reference. A platform badge alone is insufficient.
2. Capture source-native ID, canonical URL, author/account ID, full available
   text, thread/reply/quote relationship, media hashes, timestamps, retrieval
   method, and verification state, subject to licence and privacy limits.
3. Resolve quoted material to its original context. If the parent, thread, or
   linked primary material is unavailable, mark context incomplete.
4. Treat deletion as a state transition, not proof of falsity or truth. Preserve
   only metadata/content the licence and law allow, record `deleted_observed_at`,
   and remove the item from current factual status.
5. Detect likely coordination using transparent integrity indicators, but never
   translate volume, sentiment, or coordination scores into trade direction.
6. Require primary-source confirmation before a social claim becomes a fact.
   A genuinely authenticated company/executive post can be T2, but ambiguous
   posts remain T5 and cannot carry inferred financial meaning.

Social data must be ignored as a factual or trade input when identity is
unverified, provenance is a screenshot or copy, context is incomplete,
timestamps are missing, the item is outside the freshness limit, symbol/entity
mapping is ambiguous, access terms forbid the intended use, deletion/edit state
cannot be reconciled, manipulation is suspected, or required audit fields
cannot legally be retained.

Aggregate social sentiment is observational research data only. It must remain
isolated from `BUY`/`SELL`, confidence increases, position-size increases, and
block cancellation.

## 10. Explainability contract

Every news-driven warning or restriction stores and can display:

- source name, trust level, source-native ID, canonical URL, and provenance;
- exact headline as observed (subject to display rights);
- normalized event type and primary/secondary tags;
- `event_at`, `published_at`, `first_seen_at`, `ingested_at`, `updated_at`, and
  timestamp confidence;
- severity and scope;
- affected tickers plus mapping method/version and confidence;
- exact rule ID, rule version, matched inputs, and precedence path;
- user-facing explanation written without directional prediction;
- action imposed, start time, expiry, and expiry basis;
- verification, conflict, duplicate, correction, and revision state.

Example explanation:

> New exposure in ABC is blocked until 14:30 UTC because verified earnings are
> scheduled for 13:30 UTC. Rule `EARNINGS_INTRADAY_BLACKOUT/v1` applies from 60
> minutes before through 60 minutes after the release. This restriction does
> not predict price direction.

If display rights prohibit a headline, show a licensed identifier and a
generated factual description that does not reconstruct protected text.

## 11. Audit trail and conceptual data model

The future model should be append-only at the event, observation, rule
evaluation, and decision-link layers.

### Required entities and fields

**Source**

- `source_id`, name, source type, trust level and reason;
- retrieval channel, authentication method, terms/licence version;
- source timezone, health state, and validity interval.

**Raw observation**

- `observation_id`, source-native ID, canonical URL, content hash;
- legally retainable raw payload reference, headers/signature evidence;
- first-seen and ingestion timestamps, collector version;
- immutable storage checksum and retention class.

**Normalized event version**

- `event_id`, `event_version_id`, category, tags, entities, affected tickers;
- all timestamps and precision/confidence;
- normalized claims with units, period, currency, and data vintage;
- verification, duplicate cluster, conflict group, revision/correction state;
- parent, quote, supersedes, and related-event IDs;
- parser/model name and version, transformation trace, human-review state.

**Rule definition/evaluation**

- immutable `rule_id` and version, configuration checksum, effective interval;
- evaluation ID and decision timestamp;
- input event versions and calendar version;
- matched predicates, severity, scope, impact, start, expiry, and precedence;
- deterministic output checksum, exception/override record, actor, and reason.

**Decision linkage**

- decision/order intent ID, portfolio context hash, event snapshot watermark;
- restrictions presented, accepted outcome, and whether the action was blocked,
  reduced, paper-only, risk-reducing, or unaffected;
- upstream signal provenance sufficient to prove news did not create direction.

History must be immutable: corrections append; reclassification appends; manual
overrides append and never delete the original outcome. Use synchronized clocks,
monotonic ingestion sequencing, access controls, encryption, retention policy,
and checksums. Replay must reproduce what the engine knew at a historical
decision time, including outages and late arrivals.

**Open questions:** retention duration, permitted raw-content storage, who may
override S3/S4, override expiry, privacy/data-subject handling, clock authority,
and the boundary between operator annotation and source evidence.

## 12. Licensing, legal, and compliance questions

Legal review is required before acquisition, storage, display, or production
use. Unresolved questions include:

- Do ingestion, normalization, derived fields, model use, and automated trading
  use fit each provider licence?
- May headlines, excerpts, full text, transcripts, analyst research, images,
  and social posts be displayed to users, and with what attribution/linking?
- May source content and deleted/edited posts be archived for replay and audit?
  For how long, in which regions, and must deletions propagate?
- Do social-data terms permit collection, enrichment, sentiment analysis,
  persistent IDs, user/account profiling, and trading-related use?
- What redistribution, caching, concurrency, derived-data, audit-copy,
  disaster-recovery, and post-termination rights exist?
- Do exchange, issuer-IR, government, and regulatory sources impose separate
  licences, rate limits, or fair-access requirements despite public access?
- Which provider licences cover affiliates, contractors, environments, users,
  instruments, and geographic territories?
- Which copyright, database-right, privacy, defamation, market-abuse,
  recordkeeping, and consumer-protection regimes apply by jurisdiction?
- Does use of social identity/location or inferred sentiment process personal
  data, and what lawful basis, notices, deletion, and access controls follow?
- Could user-specific warnings, sizing restrictions, explanations, or overrides
  constitute personalised advice, discretionary management, solicitation, or a
  regulated recommendation?
- What obligations apply to material non-public information, rumors, embargoed
  releases, accidental early publication, and suspicious manipulation?
- Which records must be retained for regulators, and can those duties coexist
  with provider deletion and storage restrictions?

No source or provider is selected or recommended. Technical suitability does not
resolve contractual or regulatory permission.

## 13. Validation plan

Validation must be pre-registered, point-in-time, and focused on safety behavior,
not claimed predictive edge.

### Dataset construction

1. Build a versioned event corpus containing source observations, revisions,
   duplicates, conflicts, schedule changes, outages, and arrival timestamps.
2. Reconstruct only information available at each historical decision time.
   Preserve the first-seen path and later corrections as separate versions.
3. Include quiet periods, ordinary announcements, false/withdrawn reports,
   deleted posts, symbol changes, corporate actions, early closes, and stress
   episodes to prevent event-only sampling.
4. Split chronologically and by event instance; keep all duplicates and
   revisions of one event in the same split.
5. Label event identity, verification, scope, and rule applicability separately
   from subsequent returns. Human labels require written guidance and
   disagreement tracking.

### Tests and acceptance questions

**Reduces event losses**

- Compare a frozen baseline decision stream with the same stream gated by the
  candidate layer.
- Measure loss and tail-loss distributions for exposure opened or increased
  inside event windows, separately by category and severity.
- Attribute changes to blocked exposure, size caps, and risk caps without
  presenting association as causation or predictive edge.
- Test whether avoided losses are offset by new execution or concentration
  risks; predefine statistical methods before viewing outcomes.

**Avoids overblocking**

- Measure blocked eligible decisions, blocked time, affected-instrument time,
  false/withdrawn-report blocks, expiry extensions, and opportunity-cost
  distributions.
- Review quiet-period false positives and issuer-mapping spillover.
- Require coverage by event category and severity; averages must not hide a rule
  that blocks nearly all activity.

**Remains deterministic**

- Golden tests: identical event snapshot, clock, calendar, mapping, and rule
  version produce byte-identical outputs.
- Replay tests across duplicate ordering, late arrivals, retries, restarts, time
  zones, daylight-saving transitions, and source outages.
- Property tests: adding duplicates cannot raise severity; sentiment cannot
  create direction; stale items cannot become fresh without a new observation;
  lower-trust data cannot cancel a higher-trust restriction.
- Record and compare rule/configuration checksums.

**Prevents look-ahead bias**

- Enforce availability time using `published_at`, `first_seen_at`, and
  `ingested_at`; exclude any later revision from earlier decisions.
- Use the calendar version known at the time, not today's corrected calendar.
- Freeze consensus vintages and membership before a release if surprise is
  studied.
- Audit suspiciously low latency, timestamp inversions, revised archives, and
  backfilled entity mappings.

**Does not treat sentiment as fact**

- Trace every factual claim to an allowed primary/confirmed source.
- Assert that sentiment fields are absent from direction, confidence-increase,
  size-increase, stop-loosening, and block-cancellation paths.
- Use adversarial fixtures for bot swarms, impersonation, sarcasm, quote loss,
  deleted posts, coordinated pumps, and repeated syndication.
- Verify that anonymous posts and unverified social items are ignored as facts.

### Staged evaluation

1. Static corpus and rule-unit validation.
2. Historical point-in-time replay with frozen rules.
3. Shadow mode that logs constraints without affecting decisions.
4. Paper-only prospective observation through multiple event types and failure
   scenarios.
5. Independent risk, legal, licensing, and operational review before any
   consideration of live influence.

Promotion criteria, sample sufficiency, thresholds, and override policy are
**open questions**. A favorable backtest is insufficient: it may reflect
selection bias, regime dependence, data leakage, or chance. No live rollout is
authorized by this document.

## 14. Consolidated open questions

Before implementation, owners must resolve:

- instrument and jurisdiction scope, entity mapping, and cross-asset contagion;
- approved sources, trust evidence, redundancy, latency, and outage behavior;
- category-specific freshness, blackout, cooldown, and severity thresholds;
- exact meaning of risk-reducing actions and handling of existing positions;
- overnight earnings exposure and exceptions;
- market-health measures and authority to release emergency halts;
- consensus-data provenance and whether “surprise” is needed at all;
- social retention, identity verification, privacy, and deletion handling;
- every licensing and legal issue in Section 12;
- immutable retention, override governance, review ownership, and appeal paths;
- pre-registered validation criteria and independent approval.

Until those questions are resolved, the framework remains a research
specification and must not influence live trading.

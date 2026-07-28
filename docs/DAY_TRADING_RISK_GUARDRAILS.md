# Day-Trading Risk and Event-Risk Guardrails

Status: design specification only

Scope: future intraday equities engine

Default posture: fail closed

Live-money status: prohibited until every enablement criterion in this document is met

This document defines product and engineering controls. It does not claim legal,
regulatory, exchange, broker, or data-provider compliance. Where those obligations
are unresolved, they are listed separately at the end.

## 1. Operating modes

The engine has four explicit policy profiles. An account has exactly one profile.
Changing profile requires no open orders or positions, a new risk session, an audit
event, and re-acknowledgement of the applicable disclosures.

| Profile | Execution venue | Intended user | Risk posture |
|---|---|---|---|
| Beginner Mode | Paper only | New user | Most restrictive; no short selling |
| Advanced Mode | Paper only | Experienced user | Wider paper limits; short simulation allowed |
| Paper Trading | Paper only | Testing/automation baseline | Conservative deterministic test profile |
| Future live trading | Broker | Approved users only | Disabled by default; hard account and system controls |

Beginner and Advanced are product-facing paper profiles. Paper Trading is the
non-user-specific baseline for automated tests, demos, and accounts without a
selected experience profile. Future live trading is a separate profile, not a
toggle layered onto a paper profile.

All percentages use the start-of-day risk equity (`SOD_RE`) captured at 09:25:00
America/New_York (ET), or at session initialization if later. `SOD_RE` is the
lesser of broker-reported net liquidation value and risk-service equity. It is
immutable for the session. All times below are ET on a regular trading day unless
an exchange calendar says otherwise.

## 2. Global evaluation rules

1. Every new order, replacement, and cancel/re-enter request passes the complete
   pre-trade check. A replacement is evaluated as a new order before the old order
   is canceled.
2. Checks include filled positions, open orders, pending replace requests, and
   pessimistic reserved exposure. A buy reserves quantity at the greater of its
   limit price or the current ask plus allowed slippage. A short reserves at the
   greater of the limit price or current bid plus allowed slippage.
3. Market data, broker state, reference data, calendar state, news state, and risk
   state must all be healthy. Missing, conflicting, or indeterminate state blocks.
4. Hard controls cannot be overridden in-session. The only permitted response to a
   hard block is cancel, reduce, wait, or close risk. No user acknowledgement turns
   a blocked opening order into an allowed order.
5. Risk-reducing orders are allowed only when they reduce absolute position size,
   do not reverse the position, use a supported order type, and pass quote,
   duplicate-order, broker-health, and price-collar checks. During a halt or LULD
   pause they may be queued only if the broker supports held orders; otherwise they
   are blocked until trading resumes.
6. If multiple rules block an order, store every reason. The user sees the
   highest-priority reason plus “Also blocked by: …”. Priority is: kill switch or
   lockout; broker/order-state uncertainty; halt/LULD/SSR; event blackout; session
   time; stale/latency; loss/exposure; liquidity/spread/price; duplicate/slippage.
7. Timestamps use exchange-synchronized UTC internally. ET is derived using the
   IANA `America/New_York` timezone; fixed UTC offsets are forbidden.
8. Monetary values use decimal arithmetic. Maximum capacity limits permit equality
   and block values above the maximum. Loss limits are tripwires and block when
   reached. Boundary examples: a 1.00% projected daily loss breaches a 1.00% loss
   limit; risk or exposure exactly equal to its maximum is permitted; and a $5.00
   minimum-price rule permits exactly $5.00.
9. Configuration is versioned and immutable within a risk session. A more
   restrictive emergency configuration may be activated immediately and is
   audited.

## 3. Exact profile limits

| Control | Beginner Mode | Advanced Mode | Paper Trading | Future live trading |
|---|---:|---:|---:|---:|
| Maximum planned risk per trade | 0.25% SOD_RE; max $100 | 0.50% SOD_RE; max $500 | 0.25% SOD_RE; max $250 | 0.25% SOD_RE; max $250 |
| Maximum daily loss | 1.00% SOD_RE | 2.00% SOD_RE | 1.50% SOD_RE | 1.00% SOD_RE |
| Consecutive-loss limit | 2 | 3 | 3 | 2 |
| Cooldown after limit | Rest of session | 60 minutes; then one half-risk trade; next loss locks session | 30 minutes; then one half-risk trade; next loss locks session | Rest of session |
| Maximum concurrent positions | 2 | 5 | 3 | 3 |
| Maximum gross exposure | 50% SOD_RE | 100% SOD_RE | 75% SOD_RE | 50% SOD_RE |
| Maximum one-sector gross exposure | 20% SOD_RE | 35% SOD_RE | 25% SOD_RE | 20% SOD_RE |
| Maximum unknown-sector exposure | 0% | 10% SOD_RE | 0% | 0% |
| Quote age at decision | ≤1,000 ms | ≤750 ms | ≤1,000 ms | ≤500 ms |
| Quote age at broker submission | ≤1,500 ms | ≤1,000 ms | ≤1,500 ms | ≤750 ms |
| Maximum spread | lesser of $0.05 or 0.50% of mid | lesser of $0.10 or 0.75% | lesser of $0.05 or 0.50% | lesser of $0.05 or 0.35% |
| Minimum 20-day median dollar volume | $20 million | $10 million | $15 million | $25 million |
| Minimum price | $5.00 | $3.00 | $5.00 | $5.00 |
| Maximum 5-minute realized volatility | 1.50% | 2.50% | 2.00% | 1.50% |
| Opening restriction | No new risk 09:30–09:45 | No new risk 09:30–09:35 | No new risk 09:30–09:40 | No new risk 09:30–09:45 |
| Last new-risk time | 15:30 | 15:40 | 15:35 | 15:30 |
| Forced flatten deadline | 15:50 | 15:55 | 15:50 | 15:45 |
| Entry slippage limit | 10 bps | 20 bps | 15 bps | 10 bps |
| End-to-end decision latency | ≤750 ms | ≤500 ms | ≤750 ms | ≤300 ms |
| Short selling | Prohibited | Simulated, subject to SSR rules | Prohibited | Prohibited until separately approved |

Dollar caps are applied after percentage caps; the smaller planned-risk amount
wins. Future live limits can only be reduced without a new approval cycle.

## 4. Position, loss, and exposure calculations

### 4.1 Planned risk per trade

Every opening order requires a server-held protective stop price before submission.

`planned_risk = projected_quantity × abs(entry_reference - stop_price)
              + estimated_entry_fees + estimated_exit_fees
              + slippage_reserve`

For a long, `entry_reference` is the greater of order limit and current ask. For a
short, it is the lesser of order limit and current bid for price-risk distance, with
fees and slippage added separately. `slippage_reserve` is twice the profile entry
slippage limit times notional, covering entry and stop exit. Adding to a position
recalculates risk for the entire resulting position. Missing or invalid stop data,
a stop on the wrong side, or projected risk above the profile maximum blocks.

### 4.2 Daily loss

`daily_pnl = realized_pnl_after_fees
           + unrealized_pnl_at_conservative_mark
           - open_order_slippage_reserve`

Conservative mark is bid for longs and ask for shorts. New risk is blocked when
`daily_pnl <= -maximum_daily_loss` or when the order's pessimistic immediate fill
would cross that boundary. On breach, cancel all opening orders, permit only
risk-reducing orders, and lock the account for the rest of the session. The daily
state resets only after the next valid trading-day boundary and successful broker
reconciliation; restarting services never resets it.

### 4.3 Consecutive losses

A loss is a fully closed position or strategy lot whose net realized P&L after all
fees is below zero. Multiple partial exits of one position count once when the
position becomes flat. A scratch (`P&L = 0`) neither increments nor resets the
counter. A profitable close resets the counter to zero. Manual and automated trades
both count. The cooldown behavior is profile-specific in the table above.

### 4.4 Concurrent positions and exposure

A symbol counts as a position when it has non-zero quantity or an opening order
reservation. Multiple orders for one symbol count once, but their full reserved
notional counts toward exposure.

Gross exposure is the sum of absolute marked position notional plus reserved
opening notional. Sector exposure uses the same gross calculation; longs and shorts
do not offset. Reference sector is the point-in-time classification stored with the
decision. ETFs use the provider's look-through sector weights; absent look-through
data is “Unknown.” An order is blocked when its projected state exceeds
a profile maximum.

## 5. Market-data and instrument eligibility

### 5.1 Stale, crossed, locked, or invalid quotes

The quote must contain positive bid and ask, bid not greater than ask, positive
sizes, a monotonic exchange timestamp, and an allowed primary-session condition.
A locked quote (`bid = ask`) is blocked because spread and executable liquidity
cannot be assessed. Quote age is measured at both decision and broker submission
against a synchronized clock. Feed disconnect, sequence gap, timestamp regression,
clock drift above 100 ms, or breach of either quote-age threshold blocks all new
risk until three consecutive valid quote updates spanning at least one second have
arrived and the feed health check passes.

### 5.2 Bid/ask spread

`spread_pct = (ask - bid) / ((ask + bid) / 2)`.

Both the absolute and percentage profile thresholds apply; exceeding either blocks.
The check is repeated immediately before submission. Exit orders are not blocked
solely by spread, but must use the emergency exit policy and price collars.

### 5.3 Dollar volume and price

Dollar volume is the split-adjusted median of `close × consolidated volume` for the
20 completed trading sessions preceding today. Fewer than 20 valid sessions blocks.
Today's volume is never substituted. Price is the current mid; for an opening buy,
the ask must also meet the minimum; for a short, the bid must meet it. OTC
securities, preferred shares, rights, warrants, units, and instruments without a
verified US-listed common-stock or approved ETF classification are ineligible.

## 6. Volatility, halts, LULD, and short sales

### 6.1 Volatility control

Five-minute realized volatility is
`(high_5m - low_5m) / prior_5m_close`, using complete one-second bars. Missing bars
block. Reaching the profile maximum blocks new risk for 10 minutes. Re-entry
requires five continuous minutes below 80% of the threshold. A one-minute move of
3.00% or more, in either direction, blocks every profile for 15 minutes regardless
of the five-minute measure.

### 6.2 Trading halts

Any regulatory, exchange, volatility, news-pending, operational, or unknown halt
blocks new, replacement, and ordinary cancel/re-enter orders in the symbol. Opening
orders are canceled when broker rules permit. On resumption, new risk remains
blocked for 10 minutes in Beginner, Paper, and live, and 5 minutes in Advanced.
Unknown halt status is treated as halted.

### 6.3 LULD pauses

An active Limit Up-Limit Down pause, straddle state, or price within 0.25% of either
LULD band blocks new risk. After a pause ends, require 5 minutes of continuous
trading, valid bands, and volatility below the profile threshold. Orders may not be
priced outside the current bands. Missing or stale LULD bands block new risk.

### 6.4 Short-sale restrictions

Shorts are always blocked in Beginner and baseline Paper. Future live shorts remain
blocked until the separate live-short approval criteria are completed. Advanced
paper shorts require:

- verified easy-to-borrow simulation status before each order;
- no unresolved locate or borrow state;
- when Rule 201/SSR status is active or unknown, a simulated limit price strictly
  above the current national best bid;
- no short entry during halts, LULD states, event blackouts, or opening restrictions;
- borrow fee and recall risk included in simulated P&L.

An SSR status transition invalidates queued short orders and forces re-evaluation.

## 7. Session timing and overnight prohibition

Only regular-session orders between 09:30 and 16:00 are supported. Pre-market,
after-hours, market-on-open, market-on-close, and extended-hours flags are blocked.
The opening and last-new-risk times are in the profile table. On scheduled early
closes, subtract the same offsets from the official close; for example, the live
forced-flatten deadline is 15 minutes before the early close.

At the forced-flatten deadline:

1. cancel every opening order;
2. cancel and replace unfilled ordinary exits with broker-supported, marketable
   limit exits inside current price collars;
3. poll broker state until flat;
4. trigger the emergency kill switch if any position remains five minutes before
   the official close;
5. escalate for manual broker intervention if any position remains two minutes
   before the close.

No strategy may intentionally hold overnight. A position still open at the official
close is a critical incident: lock the account, page operations, reconcile with the
broker, and prohibit the next session until the incident is resolved and reviewed.

## 8. Company and macro event risk

Event data must identify source, publication time, effective time, revision, and
confidence. Missing, stale, conflicting, or unconfirmed calendar state fails closed.
All event blocks apply to opening and adding orders; risk-reducing exits remain
allowed.

### 8.1 Earnings

For the traded issuer and any constituent representing 20% or more of an ETF:

- scheduled before-market earnings: block from 15:30 on the prior trading day
  through 10:30 on release day;
- scheduled after-market earnings: block from 14:00 on release day through 10:30
  on the next trading day;
- exact release time known during market hours: block from 60 minutes before
  through 60 minutes after release;
- release time unknown or “date only”: block the entire release date plus from
  14:00 on the prior trading day through 10:30 on the next trading day;
- preliminary results, guidance updates, investor-day material financial updates,
  or rescheduled earnings use the same window as an intraday release.

An existing position at blackout start must be closed before the window begins.

### 8.2 Breaking news

High-severity symbol news includes earnings or guidance, merger/acquisition,
bankruptcy, financing, material litigation or regulatory action, clinical-trial or
drug decisions, cybersecurity incidents, executive departure, restatement, product
recall, trading-halt news, or provider severity “high.” It blocks new risk from the
earliest provider timestamp through 30 minutes after the latest related update.
Re-entry additionally requires valid trading for 10 minutes, normalized volatility,
and no halt/LULD condition.

Market-wide breaking news marked high severity blocks all new risk for 15 minutes
after the latest update. Unclassified breaking news with a symbol match blocks for
10 minutes pending classification. News-feed disconnection or age above 60 seconds
blocks new risk. Social media alone cannot clear or shorten a block.

### 8.3 Economic calendar

Tier-1 US events are CPI, core CPI, PCE/core PCE, Employment Situation/NFP,
unemployment rate, GDP advance estimate, retail sales, ISM manufacturing/services,
JOLTS, and Treasury refunding announcements. All profiles block new risk from 10
minutes before through 15 minutes after the scheduled release. Existing positions
must be closed by five minutes before the event in Beginner and live; Advanced and
Paper may retain positions only when their combined planned risk is at or below half
the normal per-trade cap.

An event released early extends the block from actual publication time. A delayed
event stays blocked until 15 minutes after confirmed publication. A canceled event
requires confirmation from the authoritative calendar source before the block ends.

### 8.4 Federal Reserve

For scheduled FOMC rate decisions, minutes, and Chair press conferences, block new
risk from 30 minutes before through 30 minutes after the last scheduled component.
All positions must be flat 15 minutes before in Beginner and live, and 5 minutes
before in Advanced and Paper. Unscheduled Federal Reserve announcements or Chair
remarks classified high severity trigger a market-wide 30-minute block from the
latest update. Re-entry requires 10 minutes below 80% of the volatility threshold.

## 9. Order integrity and execution controls

### 9.1 Supported orders and slippage

Opening market orders, stop-market entries, discretionary orders, hidden orders,
and unsupported time-in-force values are prohibited. Entries use day limit orders.
Protective exits may use broker-supported stop-limit or marketable-limit logic with
a bounded emergency policy.

Entry slippage is measured against the decision-side NBBO: fill minus ask for buys,
or bid minus fill for sells, divided by the reference price. Before submission, an
order is blocked if its limit permits slippage beyond the profile threshold. During
fills, if volume-weighted slippage exceeds the threshold, cancel the remainder,
retain the protective exit for filled quantity, and block new risk in that symbol
for 15 minutes. Exit slippage is audited but never causes an exit to be abandoned.

### 9.2 Latency

End-to-end latency runs from the newest market/event input used by the decision to
broker acknowledgement. Pre-submit estimated latency exceeding the profile limit
blocks the order. Acknowledgement exceeding the limit creates an uncertain-order
state: block all new orders, query broker order state, and reconcile before
continuing. Market-data clock drift above 100 ms or risk/broker clock drift above
250 ms activates the system kill switch.

### 9.3 Duplicate-order prevention

Every intent has a globally unique `client_order_id` and deterministic idempotency
key:

`SHA-256(account_id | strategy_id | symbol | side | position_effect |
signal_id | rounded_quantity | limit_price | risk_session_id)`.

The risk service atomically records the key before submission. A matching key,
client order ID, or equivalent active intent within the same risk session blocks.
Retries reuse the original identifiers and first reconcile with the broker. A new
signal must have a new signal ID and must still pass a 2-second per-account/symbol/
side debounce. Unknown submission outcome blocks the account until reconciliation.

### 9.4 Partial fills

Each fill immediately updates position, cash, exposure, P&L, and protective-stop
quantity. The unfilled remainder retains its original risk reservation. If the
recalculated complete-order risk or any exposure limit is reached, cancel the
remainder. If a protective order cannot be acknowledged within 2 seconds of an
entry fill in paper or 1 second in future live, cancel the remainder and initiate a
risk-reducing exit for filled quantity. Partial fills may never be rounded up, and
a fill after cancellation is handled as an unexpected fill and reconciled before
new risk is allowed.

### 9.5 Rejections and emergency kill switch

One ordinary broker rejection blocks that order and requires refreshed validation.
Two rejections for the same account within 60 seconds, any rejection classified
“risk,” “buying power,” “account restricted,” or “duplicate,” or any malformed/
unknown rejection activates an account kill switch.

The system kill switch activates on broker disconnect over 2 seconds, market-data
or event-state failure, clock drift breach, state divergence, inability to persist
an audit record, duplicate/unknown order state, protective-order failure, position
at the close, or operator activation. Activation atomically:

1. blocks every new-risk request before it reaches the broker;
2. cancels all opening orders;
3. preserves or submits risk-reducing exits when broker connectivity permits;
4. snapshots broker, order, position, quote, event, and risk state;
5. pages operations and records a critical audit event.

Only an authorized two-person operations approval may clear a future-live system
kill switch, after broker reconciliation, root-cause documentation, and a successful
read-only health check. Paper switches require one authorized operator. A service
restart, deployment, date change, or user action cannot clear a switch.

## 10. Account lockout

A hard account lockout occurs after daily-loss breach, live consecutive-loss breach,
kill-switch activation, broker-risk rejection, unreconciled order/position state,
attempted control bypass, overnight position, or audit persistence failure.

While locked, new risk and profile changes are prohibited. Cancels and verified
risk-reducing actions remain available. Session-loss and consecutive-loss lockouts
cannot clear before the next regular trading session. Every other lockout requires
state reconciliation and operator review. Future live additionally requires two
authorized approvers, neither of whom initiated the blocked trade. All unlocks
store reason, evidence, approvers, time, and before/after state.

## 11. Canonical block reasons and user explanations

Messages are exact templates. Braced values are populated from the audited decision
using user-local currency formatting and ET timestamps. The engine must not expose
provider credentials, internal stack traces, or unsupported promises.

| Code | Exact user-facing explanation |
|---|---|
| `RISK_PER_TRADE_MAX` | “Order blocked: projected trade risk is {projected_risk}, above your {limit} maximum. Reduce quantity or tighten a valid protective stop.” |
| `DAILY_LOSS_MAX` | “Trading locked for today: your daily loss is {daily_loss}, at or beyond the {limit} limit. You may only reduce or close positions.” |
| `CONSECUTIVE_LOSSES_MAX` | “New trades paused after {count} consecutive losses. The pause ends {resume_condition}.” |
| `POSITION_COUNT_MAX` | “Order blocked: it would create {projected_count} concurrent positions; this mode allows at most {limit}.” |
| `GROSS_EXPOSURE_MAX` | “Order blocked: projected gross exposure is {projected_exposure}, above the {limit} maximum.” |
| `SECTOR_EXPOSURE_MAX` | “Order blocked: projected {sector} exposure is {projected_exposure}, above the {limit} maximum.” |
| `SECTOR_UNKNOWN` | “Order blocked: sector classification is unavailable or exceeds the Unknown-sector allowance.” |
| `QUOTE_STALE` | “Order blocked: the latest quote is {quote_age_ms} ms old; this mode requires {limit_ms} ms or less.” |
| `QUOTE_INVALID` | “Order blocked: the current bid/ask quote is invalid, locked, crossed, or incomplete.” |
| `DATA_FEED_UNHEALTHY` | “Order blocked: required market data is disconnected, incomplete, or out of sequence.” |
| `SPREAD_MAX` | “Order blocked: the bid/ask spread is {spread_abs} ({spread_pct}), above the allowed {limit_abs} or {limit_pct}.” |
| `DOLLAR_VOLUME_MIN` | “Order blocked: 20-day median dollar volume is {value}; this mode requires at least {limit}.” |
| `DOLLAR_VOLUME_HISTORY` | “Order blocked: 20 complete trading sessions of dollar-volume history are not available.” |
| `PRICE_MIN` | “Order blocked: the executable price is {price}; this mode requires at least {limit}.” |
| `INSTRUMENT_INELIGIBLE` | “Order blocked: this instrument type is not eligible for day trading.” |
| `VOLATILITY_MAX` | “Order blocked: measured volatility is {value}, at or above the {limit} limit. Recheck after {eligible_time}.” |
| `TRADING_HALT` | “Order blocked: {symbol} is halted or its halt status is unknown. New trades remain paused until the post-halt waiting period ends.” |
| `LULD_PAUSE` | “Order blocked: {symbol} is paused, in a LULD straddle, or too close to a price band.” |
| `SSR_SHORT_BLOCK` | “Short order blocked: short-sale restriction or borrow status does not permit this order.” |
| `SHORTS_DISABLED` | “Order blocked: short selling is disabled in this mode.” |
| `SESSION_NOT_REGULAR` | “Order blocked: day-trading orders are allowed only during the regular market session.” |
| `OPENING_WINDOW` | “Order blocked: new positions are paused after the open until {eligible_time} ET.” |
| `NEW_RISK_CUTOFF` | “Order blocked: this mode does not open or add to positions after {cutoff_time} ET.” |
| `FLATTEN_REQUIRED` | “New trades are blocked: the account is in end-of-day flattening and may only close positions.” |
| `EARNINGS_BLACKOUT` | “Order blocked: {symbol} is inside its earnings-risk window from {start_time} to {end_time} ET.” |
| `BREAKING_NEWS` | “Order blocked: high-impact or unclassified breaking news affects {scope}. Recheck after {eligible_time} ET.” |
| `NEWS_FEED_UNHEALTHY` | “Order blocked: required breaking-news data is unavailable or stale.” |
| `ECONOMIC_EVENT` | “Order blocked: {event_name} creates an event-risk window from {start_time} to {end_time} ET.” |
| `FED_EVENT` | “Order blocked: a Federal Reserve event creates a risk window from {start_time} to {end_time} ET.” |
| `EVENT_DATA_UNHEALTHY` | “Order blocked: required event-calendar data is missing, stale, or conflicting.” |
| `ORDER_TYPE_UNSUPPORTED` | “Order blocked: {order_type} is not an allowed entry order type.” |
| `SLIPPAGE_MAX` | “Order blocked: permitted entry slippage is {projected_bps} bps; this mode allows at most {limit_bps} bps.” |
| `LATENCY_MAX` | “Order blocked: decision-to-broker latency is {latency_ms} ms; this mode requires {limit_ms} ms or less.” |
| `CLOCK_UNSYNCHRONIZED` | “Trading paused: system clocks are not synchronized within the required tolerance.” |
| `DUPLICATE_ORDER` | “Order blocked: an equivalent order is already pending or was just submitted.” |
| `ORDER_STATE_UNKNOWN` | “Trading paused: the broker outcome of a prior order is unknown and must be reconciled.” |
| `PARTIAL_FILL_RISK` | “Order remainder canceled: the partial fill reached a risk limit or lacks confirmed protection.” |
| `BROKER_REJECTION` | “Order rejected by the broker: {safe_broker_reason}. Trading may remain paused while account state is checked.” |
| `PROTECTIVE_STOP_INVALID` | “Order blocked: a valid protective stop is required and must be on the loss side of the entry.” |
| `RISK_STATE_UNAVAILABLE` | “Trading paused: account risk, position, cash, or order state is unavailable or inconsistent.” |
| `AUDIT_WRITE_FAILED` | “Trading paused: the required risk decision record could not be stored.” |
| `KILL_SWITCH_ACTIVE` | “Trading is paused by the emergency safety control. You may only cancel or reduce positions while the account is reconciled.” |
| `ACCOUNT_LOCKED` | “Trading is locked: {safe_lock_reason}. New positions remain disabled until {unlock_condition}.” |
| `LIVE_TRADING_DISABLED` | “Live-money execution is not enabled for this account. This order was not sent to a broker.” |

## 12. Audit record for every blocked order

The block record is append-only and must be durably committed before returning the
block response. Failure to write it activates `AUDIT_WRITE_FAILED`. Store these
fields exactly; nullable fields require a `null_reason`.

### Identity and policy

- `block_event_id` (UUIDv7)
- `correlation_id`, `request_id`, `client_order_id`, `idempotency_key`
- `account_id` and `user_id` as internal pseudonymous identifiers
- `strategy_id`, `strategy_version`, `signal_id`
- `risk_session_id`, `trading_date_et`
- `profile` (`BEGINNER`, `ADVANCED`, `PAPER`, `FUTURE_LIVE`)
- `execution_environment` (`PAPER`, `LIVE_DISABLED`, `LIVE`)
- `policy_version`, `policy_sha256`, `config_version`
- `decision_service_version`, `decision_host_id`

### Requested order

- `symbol`, `asset_id`, `instrument_type`, `primary_exchange`
- `side`, `position_effect`, `order_type`, `time_in_force`
- `requested_quantity`, `requested_notional`, `limit_price`, `stop_price`
- `extended_hours`, `submitted_at_utc`, `received_at_utc`, `decision_at_utc`

### Complete risk snapshot

- `sod_risk_equity`, `current_equity`, `available_buying_power`
- `realized_pnl`, `unrealized_pnl`, `daily_pnl`, `daily_loss_limit`
- `consecutive_losses`, `consecutive_loss_limit`, `cooldown_until_utc`
- `planned_risk`, `trade_risk_limit`, `slippage_reserve`
- `current_position_count`, `projected_position_count`, `position_count_limit`
- `current_gross_exposure`, `projected_gross_exposure`, `gross_exposure_limit`
- `sector`, `sector_source`, `current_sector_exposure`,
  `projected_sector_exposure`, `sector_exposure_limit`
- `current_symbol_position`, `open_order_reserved_quantity`,
  `open_order_reserved_notional`
- `account_lock_state`, `kill_switch_state`

### Market and reference snapshot

- `bid`, `ask`, `bid_size`, `ask_size`, `mid`, `spread_abs`, `spread_pct`
- `quote_exchange_time_utc`, `quote_received_time_utc`, `quote_age_ms`,
  `quote_sequence`, `quote_conditions`
- `market_data_provider`, `market_data_feed_status`
- `clock_offset_ms`, `decision_latency_ms`, `estimated_submit_latency_ms`
- `price`, `minimum_price`, `median_20d_dollar_volume`,
  `minimum_dollar_volume`, `valid_volume_session_count`
- `realized_volatility_1m`, `realized_volatility_5m`,
  `volatility_limit`, `volatility_cooldown_until_utc`
- `halt_status`, `halt_reason`, `halt_source`, `halt_resume_time_utc`
- `luld_state`, `luld_lower_band`, `luld_upper_band`,
  `luld_source_time_utc`
- `ssr_status`, `ssr_source_time_utc`, `borrow_status`, `borrow_source`

### Calendar and news snapshot

- `market_session_status`, `official_open_utc`, `official_close_utc`,
  `is_early_close`
- `earnings_event_id`, `earnings_release_time_utc`,
  `earnings_timing_confidence`, `earnings_blackout_start_utc`,
  `earnings_blackout_end_utc`
- `news_event_ids`, `news_severity`, `news_scope`,
  `latest_news_time_utc`, `news_provider_status`
- `economic_event_ids`, `economic_event_names`,
  `economic_blackout_start_utc`, `economic_blackout_end_utc`
- `fed_event_ids`, `fed_blackout_start_utc`, `fed_blackout_end_utc`
- `calendar_provider`, `calendar_as_of_utc`, `calendar_status`

### Decision and operational evidence

- `primary_block_code`, `all_block_codes`
- `rule_thresholds` (canonical JSON), `observed_values` (canonical JSON)
- `user_message_template_version`, `rendered_user_message`
- `decision` (always `BLOCK`)
- `risk_reducing_order` (boolean)
- `broker_submission_attempted` (must normally be false)
- `broker_order_id`, `broker_response_code`, `safe_broker_response`
- `duplicate_of_block_event_id`, `duplicate_of_order_id`
- `state_snapshot_uri`, `state_snapshot_sha256`
- `trace_id`, `span_id`
- `created_at_utc`, `retention_class`
- `null_fields` (array of field names), `null_reasons` (field-to-reason map)

Raw provider payloads, credentials, access tokens, full personal data, and
unredacted broker messages must not be stored in this record. Source payloads may
be held separately under an approved retention and access policy and referenced by
hash.

## 13. Criteria before live-money execution may ever be enabled

Live execution remains hard-disabled in code, configuration, broker permissions,
and account state until all items are evidenced and approved:

1. Legal counsel has resolved every legal question below for each intended
   jurisdiction and documented required disclosures, agreements, licensing, and
   record-retention duties.
2. The broker has approved the use case and account/order flows in writing; account
   restrictions, buying-power behavior, short-sale behavior, fractional shares,
   cancel/replace semantics, and incident contacts are tested.
3. Every market, reference, corporate-action, earnings, news, economic-calendar,
   halt, LULD, and SSR data provider has contractually permitted the intended use
   and supplied documented latency, coverage, redistribution, and outage behavior.
4. A production risk service independent of strategy logic enforces every hard
   rule server-side and fails closed. Client-side checks are never authoritative.
5. Unit, property, integration, replay, concurrency, time-zone/DST, early-close,
   chaos, broker-sandbox, and end-to-end tests cover every allow/block boundary and
   every canonical reason code with no unresolved severity-1 or severity-2 defects.
6. At least 60 trading days and 1,000 representative trades complete in paper
   shadow mode using production-equivalent data and order flow, with zero escaped
   hard-limit breaches, zero unreconciled duplicate orders, and 100% block-audit
   persistence.
7. Independent risk review validates calculations, pessimistic reservations,
   event windows, recovery paths, and inability of strategy or UI code to bypass
   the controls.
8. A security review covers authentication, authorization, least privilege,
   secrets, tamper-evident audit storage, operator actions, supply chain, alerting,
   and incident response; all critical/high findings are closed.
9. Broker-versus-ledger reconciliation is proven at startup, continuously, after
   every uncertain outcome, and at close. Any mismatch demonstrably blocks new risk.
10. Kill-switch, cancel-all, flatten, broker-disconnect, stale-data, late-fill,
    partial-fill, rejected-order, and overnight-position drills succeed in a broker
    sandbox and controlled production-readiness exercise.
11. Monitoring and paging have named owners and measured alerts for data freshness,
    latency, reject rate, reconciliation, loss limits, partial fills, protective
    orders, lockouts, and positions approaching the close.
12. Operations has a staffed runbook, broker escalation path, two-person live
    unlock process, rollback plan, and documented authority to halt all execution.
13. User eligibility, identity/account linking, risk disclosures, affirmative
    consent, profile suitability process, and support/escalation flows are approved
    by counsel and implemented.
14. Live rollout is separately authorized in a recorded go/no-go review by product,
    engineering, security, operations, risk, and legal owners. Approval identifies
    exact accounts, symbols, dates, capital, and configuration version.
15. Initial live scope uses an allowlist, no short selling, no extended hours, at
    most the Future live limits in this document, and a separately approved capital
    cap. Expansion requires a new review with observed evidence.
16. The live feature has independent code and infrastructure controls that default
    off, require two authorized approvers to enable, expire automatically, and are
    verified against the broker account before the first order.

Passing these criteria permits a go/no-go decision; it does not itself authorize or
guarantee live launch.

## 14. Unresolved decisions and external questions

### Legal and policy questions

- Which jurisdictions and user types may access paper features and any future live
  feature, and what licensing or registration analysis applies?
- Could signals, automation, personalization, order routing, or account control be
  treated as investment advice, brokerage, discretionary management, or another
  regulated activity?
- Which day-trading, margin, cash-account settlement, good-faith violation,
  suitability, best-execution, disclosure, consent, supervision, complaint, and
  books-and-records obligations apply at launch time?
- What identity, age, sanctions, AML/KYC, privacy, data residency, accessibility,
  retention, deletion, surveillance, and tax-reporting duties apply, and which
  party owns each duty?
- What disclosures are required for automated execution, simulated performance,
  outages, slippage, partial fills, halts, event data, and loss of connectivity?
- What human review and user appeal process is required for account restrictions,
  lockouts, erroneous trades, complaints, and incident remediation?
- How long must decision, communication, market-data, and order records be retained,
  in what immutable form, and who may access or export them?

### Broker questions

- Which broker and account types will be used, and what are the exact buying-power,
  margin, settlement, day-trading, fractional-share, minimum-notional, and order-rate
  rules?
- Does the broker offer server-held protective orders, OCO/bracket atomicity,
  idempotent submission, cancel-all, kill-switch, drop-copy, and authoritative
  execution reports?
- What are the broker's precise behaviors for timeouts, duplicate client IDs,
  replace races, cancel-pending fills, busts/corrections, halts, LULD, early closes,
  corporate actions, and marketable-limit exits?
- What live short-sale permissions, locate workflow, easy-to-borrow feed, SSR
  enforcement, borrow fees, recall handling, and close-out duties would apply?
- Which broker states are authoritative for equity, buying power, positions, open
  orders, restrictions, and trading calendar, and what are their freshness SLAs?
- What are the broker's incident contacts, rate limits, maintenance windows,
  sandbox fidelity, error taxonomy, and financial responsibility for erroneous
  execution?

### Data-provider questions

- Which consolidated real-time quote entitlement and redistribution rights are
  required for each user, display, derived metric, audit record, and automated use?
- Which sources are authoritative for exchange calendars, early closes, halts,
  LULD bands, SSR status, corporate actions, sector classifications, earnings,
  breaking news, and economic/Federal Reserve events?
- What are coverage, correction, timestamp, sequence, latency, uptime, failover,
  historical backfill, and incident-notification guarantees for each source?
- May raw or derived provider data be retained in risk audits, for how long, and
  may it be shown to users or reviewers?
- How will conflicting sources be prioritized, and what independent fallback source
  is contractually and technically available?
- Can event classifications and ETF look-through data be used for automated blocking,
  and how quickly are revisions and constituent changes delivered?

### Product and risk decisions

- What separately approved absolute live capital cap and per-account rollout size
  should apply below the limits in this specification?
- Will live trading initially support only whole-share US common stocks, or an
  approved ETF allowlist as well?
- Who fills each named approval role, operates the two-person unlock, owns incident
  response, and has authority to keep live execution disabled?
- What objective evidence would justify changing a threshold after launch, and what
  change-control and user-notification process is required?

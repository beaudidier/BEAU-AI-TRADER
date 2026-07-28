# First-time user clarity review

## Objective and guardrails

This review asks whether a person with no trading knowledge can understand the product's next action in 15 seconds. It changes presentation only. Strategy logic, scoring, entries, stops, targets, position limits, and market-regime logic remain unchanged.

## Executive finding

The production product was built as an analyst workstation, not a beginner decision aid. Its first screen answered “what did the system calculate?” before “what should I do now?”. A new user saw several opportunities, confidence badges, recommendations, R multiples, scanners, strategy status, and beta-readiness information at the same time. The most dangerous interpretation was that a high score or “BUY” meant “buy now,” even when the setup was waiting for a lower entry.

Beginner Mode now defaults to one verified setup and gives the user one status and one next action. Advanced Mode preserves the original scanner and technical detail.

## Screen-by-screen review

| Screen | Comprehension problems | Beginner risk | Resolution / recommendation |
| --- | --- | --- | --- |
| Login | “Private beta” and “professional tester” explain access, but not what the product does or that it is paper-first. | A user can enter expecting brokerage execution or guaranteed recommendations. | Keep login mechanics; add a short paper-trading orientation in a later auth-copy pass. |
| Dashboard | Several “top opportunities,” scanner controls, confidence, recommendation, R, beta readiness, briefing, and watchlist compete for attention. “What should I buy today?” implies immediate action. | High confidence can be mistaken for probability; “Analyze” does not state what happens next; pending entries look actionable. | Beginner Mode is the default. It shows one best verified setup, exact status, levels, per-share risk/reward, reason, biggest risk, and one action. Advanced Mode retains the original screen. |
| Latest signals | “Production-path replay,” “audited,” “frozen,” EMA20/50, market regime, raw-candle levels, mismatches, and qualification reasons are developer/research language. The page repeats levels in the chart and metric grids. | “Valid replay signal” can be read as a live buy instruction. Four-decimal prices imply false execution precision. | Existing wait warning is good. Default dashboard no longer sends beginners here first. Advanced evidence remains available; next pass should add a page-level mode filter. |
| Trade workspace | Three dense columns begin with a technical chart and seven-factor institutional analysis. “Paper Buy” is direct but the setup status is not the dominant heading. The chart showed support/resistance and EMAs but not the plan. | Users may buy before entry, assume reference stops execute automatically, or confuse maximum risk with guaranteed maximum loss. | Chart now marks current price, entry zone, stop zone, TP1, TP2, and signal candle. Tap/hover labels explain each. The dashboard makes the wait/act decision before this screen. |
| Paper trading | Terms such as open position, unrealized P/L, risk budget, concentration, close reason, and coach grading assume trading knowledge. | A user may believe paper stops execute like broker orders or close a position without understanding the result. | Preserve portfolio controls. The new flow reaches paper trading only after setup and risk review. A future copy-only pass should explain order simulation and P/L. |
| Historical evidence | Retrospective holdout, out-of-sample, expectancy R, drawdown R, profit factor, deterministic replay, and distribution are research terms. | Backtest outcomes may be treated as a promise of future results. Selected examples may be mistaken for all outcomes. | Keep outside the beginner critical path. Retain explicit classification. Add a beginner summary before methodology in a later evidence-focused milestone. |
| Forward validation | Evidence state, qualifying observations, confidence intervals, calibration, and frozen strategy language are statistically accurate but hard to interpret. | “Validation” can be mistaken for proof that future trades will win. Small samples can be over-trusted. | Keep outside initial flow. Lead later with “real signals observed after rules were frozen; still not a guarantee.” |
| Portfolio | Risk %, exposure, sector concentration, buying power, maximum positions, and open/closed distinctions are shown together. | Users can confuse planned loss with guaranteed loss, or think remaining cash equals safe risk capacity. | Portfolio admission blocks remain unchanged. Beginner dashboard states loss per share, quantity dependency, gap/slippage risk, and paper-first action. |
| Feedback | Setup review and product feedback are close concepts; “review signal” can sound like inspect rather than submit feedback. | Low financial danger, but intent and destination are unclear. | Rename links contextually in a later pass (“Send feedback about this setup”). |

## Terms and numbers that require explanation

- **Confidence**: a rules-based score, not win probability. This disclaimer is now persistent on both dashboard modes.
- **Entry**: the planned price that must be reached; not the current price and not an instruction to chase.
- **Stop**: the planned invalidation exit; not a guaranteed fill or hard cap on loss.
- **TP1 / TP2**: first and second rules-based profit targets; neither is guaranteed.
- **R / risk-reward**: reward expressed as a multiple of planned per-share risk.
- **Maximum risk**: depends on quantity and can be exceeded by gaps or slippage.
- **Market regime**: a rules-based market-environment gate, not a forecast.
- **Expired**: entry did not occur in the allowed window; do not reuse old levels.
- **Blocked**: the trade cannot be opened because plan or portfolio rules fail.
- **Paper trade**: a simulation, not a real brokerage order.

## Information hierarchy

Beginner Mode intentionally delays scanner universes, raw engine scores, advanced indicators, institutional radar, beta-readiness diagnostics, duplicate metrics, and research audit language. The first hierarchy is:

1. Ticker and company.
2. Exact status: waiting, ready for paper trade, blocked, or expired.
3. One next action.
4. Current price, entry, stop, TP1, and TP2.
5. Maximum planned loss and possible reward per share.
6. Why the setup exists and what can go wrong.
7. Setup → risk → paper-trade flow.

## Empty and blocked states

- **No valid setup today**: explains that waiting is the correct action.
- **Waiting for entry**: explicitly says not to buy at market and that no trade opens if entry is missed.
- **Setup expired**: labels the setup expired and removes an immediate trade action.
- **Data unavailable**: tells the user not to act until prices and levels can be verified.
- **Portfolio risk limit reached**: existing admission rules block the paper action and enumerate the reason in the workspace.

## Zero-knowledge 15-second scenario

Test prompt: “You have never traded. Look at the first screen for no more than 15 seconds, then answer without scrolling.”

Pass criteria:

- Stock: ticker and company are the largest content heading.
- Act or wait: status badge and “Your next action” appear above all metrics.
- Entry: “Planned entry” card includes a plain-language instruction.
- Maximum loss: per-share planned loss is shown, with quantity and slippage caveats.
- Target: TP1 and TP2 are shown together.
- Why: “Why this trade?” is visible in the first screen’s core explanation area.
- What could go wrong: “Biggest risk” explains gaps; invalidation explains setup failure.

At 390px, these answers remain in a single vertical reading order with no horizontal overflow. The status and next action appear before technical explanations.

## Implementation summary

- Added persistent Beginner/Advanced mode selection; first visit defaults to Beginner.
- Added a single-setup “What should I do now?” dashboard.
- Added status-specific and data/no-signal empty states.
- Added risk and reward per share without changing sizing logic.
- Added the six required plain-language explanations.
- Added the three-step beginner flow.
- Added current, entry, stop, TP1, TP2, and signal markers to the live workspace chart, with hover/tap explanations.
- Preserved all existing advanced scanner, evidence, validation, and portfolio functionality.

## Guided first-login product tour

Tour version 2 adds a 14-step, plain-language walkthrough that starts on the first authenticated dashboard visit. It covers the dashboard, best setup, status, current price, planned entry, stop, both profit targets, planned maximum loss, next action/Trade Workspace, Paper Trading with portfolio risk, Historical Evidence, Forward Validation, Feedback, and the Beginner/Advanced switch.

The tour highlights only visible DOM targets, dims the remaining screen, scrolls targets into view, and skips missing or hidden elements. The best-setup step falls back to the no-setup/data-unavailable state. On viewports below 640px the dialog is fixed above the bottom edge with 44px minimum controls; desktop placement follows the highlighted element.

### Persistence

Progress is namespaced by authenticated user ID and stores:

- `tour_started_at`
- `current_step`
- `completed_at`
- `skipped_at`
- `tour_version`

Closing with Escape or the close button keeps the current step for the next browser session. Skip prevents automatic restart, while “Restart product tour” in Profile resets progress deliberately. A changed `tour_version` is treated as a fresh major-product tour. Completed and skipped tours do not reopen automatically for the same version.

### Accessibility and safety

- Dialog semantics use `role="dialog"`, `aria-modal`, labelled title, and described content.
- Keyboard navigation supports Arrow Right/Enter, Arrow Left, Escape, and a trapped Tab sequence.
- Focus returns to the previously focused control after closing.
- Mobile controls meet a 44px minimum height.
- Highlighting uses border, position, text, and screen-reader labels rather than colour alone.
- Safety copy states that waiting is not buying, confidence is not probability, paper trading uses no real money, plan levels are not guarantees, and setups can expire or invalidate.

### Tour verification

- Frontend state tests cover first start, completed second login, skip, resume, next/back, version reset, restart, and user isolation.
- Guided-flow tests cover unavailable targets, the 390px breakpoint, keyboard mapping, all 14 final steps, and required safety phrases.
- Production build and lint pass.
- The 390px production shell has no horizontal overflow. Full authenticated tour rendering still requires a signed-in preview session; the automated mobile behavior test verifies bottom placement selection at 390px.

## Local authenticated preview verification — 2026-07-28

### Preview result

The feature branch was run locally with the FastAPI backend on port 8000 and Vite frontend on port 5173 using an existing authenticated beta-test session. The original version-1 tour automatically opened at step 1 and completed all 18 preview steps; the final version-2 pass below verifies the reduced 14-step tour.

Every final target was visible, auto-scrolled into view, and avoided dialog overlap after the targeting fixes below. The explanations matched the displayed controls. Close, browser reload/resume, Next, Back, Skip persistence, Finish, Profile restart, Arrow Right/Enter, Arrow Left, Escape/resume, and Tab/Shift+Tab focus wrapping were verified against the running app.

The zero-knowledge check passed for the live PNW setup before the stale-data guard was applied:

- Stock: PNW, Pinnacle West Capital.
- Action: wait; do not buy now.
- Entry: $106.55.
- Stop: $101.58.
- TP1 / TP2: $116.66 / $126.71.
- Planned loss: $4.97 per share before slippage and quantity effects.
- Setup reason: risk-on market plus a rules-based pullback near the signal-time EMA20.
- Invalidation: the entry window expires if price does not reach the fixed entry.
- Execution: paper trading uses no real money.
- Next click: Review chart and risk.

### Critical issues found and fixed

1. **False “Data unavailable” in local development.** React Strict Mode intentionally aborted the first signal request during its remount check, but the beginner card treated that abort as a real data failure. Aborted requests are now ignored, allowing the valid setup and its tour targets to render.
2. **Tour dialog covered highlighted regions.** Dashboard and best-setup targets were too tall, and desktop placement only attempted to position below them. Targets now identify the exact visible summary elements, while placement chooses right, left, below, or above according to available space. The original 18-step geometry audit recorded no overlap after this correction.
3. **Stale quote described as current.** The July 23 quote was still labelled “Current price” on July 28. Prices older than a conservative 120 hours now block action and show the source time explicitly. This is presentation-only and changes no entry, stop, target, score, or strategy rule.
4. **Portfolio block absent from the beginner status.** The dashboard now reads the existing portfolio-risk status and displays Blocked when the existing rules reject new risk. It does not create or modify any limit.

### State coverage

- Valid setup available: verified live with PNW.
- Waiting for entry: verified live, including the “does not mean buy now” wording.
- Stale data: verified live after the safety guard; status becomes Blocked and says not to act.
- No setup / data unavailable: verified through fallback contracts and focused tests.
- Entry ready, expired, invalidated, and portfolio-risk blocked: verified through the same presentation function used by the UI, using focused state tests.
- Missing/hidden tour targets: verified through automated skip tests and the live data-unavailable fallback before the abort fix.
- Mobile: 390px behavior, bottom placement selection, 44px targets, and hidden-target skipping pass automated tests. The connected browser ignored its requested 390×844 override and remained 1280×720, so an authenticated pixel-level 390px browser inspection could not be completed in that runtime.

### Remaining usability risks after preview

- The 120-hour stale threshold is deliberately conservative and calendar-based; a future market-calendar-aware freshness service would handle extended exchange holidays more precisely.
- Native iPhone Safari still needs the manual verification listed in the final pass below.

### Final recommendation

**Ready for a controlled user preview: yes.** The critical false-error, overlap, stale-price, and portfolio-status risks are fixed. Keep the preview paper-only and observe whether beginners abandon during the navigation/evidence section. A real-device 390px pass remains recommended before broader beta exposure because the connected browser could not apply its viewport override.

## Final beginner tour clarity pass

### Final structure and corrected targets

The final tour has **14 steps** and uses tour version 2 so users who completed the materially different version-1 tour can see the clearer walkthrough once:

1. Dashboard overview
2. Best current setup
3. Setup status
4. Current price
5. Planned entry
6. Stop loss
7. TP1 and TP2 targets
8. Maximum possible loss
9. Next action and Trade Workspace
10. Paper Trading and portfolio risk
11. Historical Evidence
12. Forward Validation
13. Feedback
14. Beginner / Advanced switch

TP1 and TP2 now share one target and explanation. Next action and Trade Workspace are one step. Paper Trading and portfolio risk are one safety step. Historical and forward evidence stay separate because they point to different real screens and answer different questions.

The unavailable Portfolio/Journal feature is omitted. The tour no longer points incorrectly to Learning and does not promise a screen that is absent on this branch.

### Jargon removed

The main “Why this trade?” explanation no longer requires technical vocabulary. A compact, optional Beginner terms section defines:

- **EMA20:** a recent average price covering about 20 trading days, weighted toward newer days.
- **EMA50:** a longer average price covering about 50 trading days, weighted toward newer days.
- **Signal-time confidence:** the rules score saved when the setup first appeared, not the chance of profit.
- **Risk-on market:** broad conditions that support taking carefully planned stock risk.
- **Market regime:** whether the broad market is generally rising, falling, or sideways.
- **Pullback:** a temporary dip inside a setup that still meets the rules.

EMA20 and EMA50 also have plain-language explanations in the chart’s tap/hover legend. Confidence wording remains explicit: it is a rules-based score, not a guaranteed probability of profit.

### Mobile Safari status

Native Safari automation was attempted but the available Mac computer-control service could not start. The connected browser also did not honor its requested iPhone viewport. Automated coverage still verifies the 390px mobile placement branch, missing/hidden target skipping, 44px controls, and keyboard behavior.

Remaining human iPhone Safari checklist:

- Open the authenticated tour in portrait at approximately 390 × 844.
- Run all 14 steps with Safari’s bottom bar expanded and collapsed.
- Confirm the bottom-fixed dialog stays above browser chrome and no text or buttons are clipped.
- Confirm Close, Back, Next, Skip, and Finish remain at least 44 × 44 CSS pixels.
- Confirm each visible target scrolls fully into view and the dialog does not cover it.
- Confirm hidden desktop navigation targets skip safely instead of producing an empty highlight.
- Rotate to landscape, continue two steps, then rotate back to portrait.
- Confirm orientation changes preserve the step, reposition the highlight, and do not create horizontal scrolling.
- Close Safari during the tour, reopen it, and confirm the same step resumes.

This checklist is the remaining human verification before broad mobile beta exposure.

### Bundle warning

The production sourcemap attributes the largest source inputs to React DOM (about 533 KiB source), Supabase Auth (about 400 KiB), React Router (about 363 KiB), application pages (about 286 KiB), and Lightweight Charts (about 183 KiB), followed by the other Supabase clients. The tour is not the dominant cause.

The app still compiles into one approximately 833 KiB minified initial chunk (about 231 KiB gzip), so Vite reports its 500 KiB warning. Lazy-loading only the small tour would not resolve it. Splitting authentication, charts, and route pages is a broader performance refactor with more regression risk than this clarity milestone, so the warning is documented as non-blocking and unchanged.

### Final verdict

**Merge-ready: yes.** The comprehension, fatigue, jargon, and incorrect-target issues are resolved; all 14 live desktop targets are visible and non-overlapping. Native iPhone Safari remains a manual pre-release check, not a blocker for merging this isolated clarity branch.

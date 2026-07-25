# Corrected Strategy Verdict

## Executable-entry result

BUY has **no credible edge** after next-open entry recalculation and gap validation. It produced **21** accepted out-of-sample trades, **-0.0531R** expectancy, **0.9282** profit factor, and **-6.3877R** chronological maximum drawdown. Its 95% bootstrap expectancy interval is **-0.7070R to 0.6137R**.

The audit rejected **12,709** invalid gap attempts. This includes 12,347 entries too far above the original setup and 11,871 cases with Target 1 R/R below 1.5; multiple reasons can apply to one attempt.

BUY does not beat WATCH (0.2197R expectancy, 1.3893 PF), all valid accepted setups (0.2675R), buy and hold (11.6403% average return), EMA20/EMA50 (1.8552% average return), or matched random entries (28.57% BUY win rate versus 41.40% random win rate).

The system remains paper-trading only. The next experiment must validate whether the proposed live entry remains executable before presenting a trade plan; no scoring, threshold, or weight experiment is justified yet.

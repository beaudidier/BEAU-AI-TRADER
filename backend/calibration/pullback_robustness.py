"""Standalone five-year robustness audit for the Milestone 28 Pullback plan.

This runner uses cached Yahoo daily data and never modifies production scoring
or execution. Run: ``PYTHONPATH=backend python3 -m calibration.pullback_robustness``.
"""
from __future__ import annotations

import csv
import json
import math
import time
from collections import Counter, defaultdict
from datetime import date, timedelta

import numpy as np
import pandas as pd

from atr import add_atr
from backtesting.execution import entry_fill_price, exit_fill_price, transaction_cost
from calibration.run_audit import MAX_HOLDING_DAYS, OUTPUT, SLIPPAGE_BPS, TRANSACTION_COST_BPS, WARMUP_BARS, _band
from engines.engine_utils import safe_float
from engines.institutional_engine import calculate_institutional_analysis
from providers import get_market_data_provider

DATASET_CACHE = OUTPUT / "pullback_robustness_dataset"
BOOTSTRAP_SAMPLES, RANDOM_SEED, MINIMUM_CANDLES, MAX_RISK_PCT = 4_000, 20260726, 1_100, .05
UNIVERSE = {
    "Technology": "AAPL MSFT NVDA AVGO ORCL CRM ADBE AMD CSCO IBM QCOM TXN INTU NOW AMAT",
    "Consumer Discretionary": "AMZN TSLA HD MCD NKE SBUX BKNG LOW TJX GM F ROST MAR ORLY",
    "Financials": "JPM BAC GS MS V MA AXP BLK CME SCHW PNC USB COF AFL",
    "Health Care": "LLY UNH JNJ ABBV MRK TMO ABT DHR ISRG AMGN GILD BMY SYK CVS",
    "Energy": "XOM CVX COP EOG SLB MPC PSX OXY KMI VLO WMB HAL DVN",
    "Industrials": "CAT GE HON UNP RTX DE LMT BA ETN ITW EMR WM GD CARR PH",
    "Consumer Staples": "WMT COST PG KO PEP PM MO CL MDLZ KHC GIS SYY KR KMB",
    "Utilities": "NEE DUK SO AEP EXC SRE D ATO EIX XEL WEC ES ED",
    "Real Estate": "AMT PLD EQIX PSA O SPG WELL DLR AVB EQR VTR BXP ARE",
    "Communication Services": "META GOOGL NFLX DIS TMUS CMCSA CHTR T VZ EA WBD LYV FOXA",
    "Materials": "LIN APD SHW FCX NEM ECL NUE DOW DD MLM VMC ALB CF",
}
# A balanced 110-name subset (ten per sector) exceeds the requested 100 while
# avoiding a technology-heavy universe. The source list remains explicit above.
SYMBOLS = {symbol: sector for sector, values in UNIVERSE.items() for symbol in values.split()[:10]}
WAIT_WINDOWS, STOP_ATRS, COST_MULTIPLIERS = (1, 3, 5), (.5, 1., 1.5), (1, 2, 3)
TARGETS = {"r15_3": (1.5, 3., .5), "r2_4": (2., 4., .5), "full_r2": (2., None, 1.)}


def _validate(data: pd.DataFrame | None, end: date) -> str | None:
    if data is None or data.empty: return "provider returned no data"
    required = {"Open", "High", "Low", "Close", "Volume"}
    if not required.issubset(data.columns): return "missing required OHLCV columns"
    values = data.loc[:, sorted(required)].apply(pd.to_numeric, errors="coerce")
    if len(values) < MINIMUM_CANDLES: return f"only {len(values)} candles; need {MINIMUM_CANDLES}"
    if values.isna().any().any() or (values <= 0).any().any(): return "invalid OHLCV values"
    if data.index.has_duplicates or not data.index.is_monotonic_increasing: return "dates are duplicated or not chronological"
    if pd.Timestamp(data.index[-1]).date() >= end: return "latest candle may be incomplete"
    return None


def _history(provider, ticker: str, start: date, end: date) -> tuple[pd.DataFrame | None, str | None]:
    DATASET_CACHE.mkdir(parents=True, exist_ok=True); cache = DATASET_CACHE / f"{ticker}.csv"
    if cache.exists():
        try:
            cached = pd.read_csv(cache, index_col=0, parse_dates=True)
            if (error := _validate(cached, end)) is None: return cached, None
        except (OSError, ValueError, pd.errors.ParserError): pass
    errors = []
    for attempt in range(1, 4):
        try:
            data = provider.get_history(ticker, interval="1d", start=start.isoformat(), end=end.isoformat())
            if (error := _validate(data, end)) is None:
                data.to_csv(cache); return data, None
            errors.append(f"attempt {attempt}: {error}")
        except Exception as error: errors.append(f"attempt {attempt}: {type(error).__name__}: {error}")
        time.sleep(.2 * attempt)
    return None, "; ".join(errors)


def _report_regime(benchmark: pd.DataFrame) -> str:
    closes = benchmark["Close"]
    if len(closes) < 200: return "Sideways"
    sma50, sma200, close = closes.rolling(50).mean().iloc[-1], closes.rolling(200).mean().iloc[-1], closes.iloc[-1]
    if close > sma200 and sma50 > sma200: return "Bull"
    if close < sma200 and sma50 < sma200: return "Bear"
    return "Sideways"


def _candidates(histories: dict[str, pd.DataFrame], benchmark: pd.DataFrame) -> list[dict]:
    records = []
    for ticker, data in histories.items():
        for index in range(WARMUP_BARS, len(data) - MAX_HOLDING_DAYS - max(WAIT_WINDOWS)):
            history, spy = data.iloc[:index + 1].copy(), benchmark.loc[:data.index[index]].copy()
            if len(spy) < WARMUP_BARS: continue
            # Every configuration uses this signal-time EMA20 limit and waits
            # at most five sessions. If no future candle can touch it, no
            # configuration can open a trade, so it needs no signal replay.
            ema20 = float(history["Close"].ewm(span=20, adjust=False).mean().iloc[-1])
            entry_window = data.iloc[index + 1:index + 1 + max(WAIT_WINDOWS)]
            if not ((entry_window["Low"] <= ema20) & (entry_window["High"] >= ema20)).any():
                continue
            try:
                analysis = calculate_institutional_analysis(history, spy); atr = safe_float(add_atr(history)["ATR"].iloc[-1])
            except (ArithmeticError, KeyError, TypeError, ValueError): continue
            if not atr or atr <= 0: continue
            records.append({"ticker": ticker, "sector": SYMBOLS[ticker], "index": index, "signal_date": str(data.index[index].date()), "confidence": int(analysis["overall_score"]), "band": _band(int(analysis["overall_score"])), "verdict": analysis["recommendation"], "ema20": ema20, "swing_low_20": float(history.tail(20)["Low"].min()), "atr": float(atr), "market_regime": _report_regime(spy)})
    records.sort(key=lambda row: (row["signal_date"], row["ticker"])); dates = [pd.Timestamp(row["signal_date"]) for row in records]
    boundaries = (dates[len(dates)//3], dates[2*len(dates)//3])
    for row in records: row["walk_forward_period"] = "Walk-forward 1" if pd.Timestamp(row["signal_date"]) < boundaries[0] else "Walk-forward 2" if pd.Timestamp(row["signal_date"]) < boundaries[1] else "Walk-forward 3"
    return records


def _simulate(data: pd.DataFrame, entry_index: int, entry: float, stop: float, target_1: float, target_2: float | None, tp1_portion: float, slippage_bps: float, cost_bps: float) -> dict | None:
    """Experimental accounting: conservative stop first and original stop after TP1."""
    shares = 100
    if not (math.isfinite(entry) and math.isfinite(stop) and entry > stop > 0): return None
    risk, entry_cost, remaining = (entry-stop)*shares, transaction_cost(entry, shares, cost_bps), shares
    tp1_hit = tp2_hit = stop_hit = False; legs = []
    def close(quantity, price, index, label):
        fill = exit_fill_price(price, slippage_bps); exit_cost = transaction_cost(fill, quantity, cost_bps)
        pnl = (fill-entry)*quantity - entry_cost*quantity/shares - exit_cost
        legs.append({"leg": label, "shares": quantity, "exit_price": fill, "exit_index": index, "pnl": pnl, "r_multiple": pnl/risk})
    last = entry_index
    for index in range(entry_index, min(len(data), entry_index+MAX_HOLDING_DAYS)):
        low, high = float(data.iloc[index]["Low"]), float(data.iloc[index]["High"]); last = index
        if low <= stop: close(remaining, stop, index, "STOP"); remaining=0; stop_hit=True; break
        if not tp1_hit and high >= target_1:
            quantity = remaining if tp1_portion == 1 else min(remaining, max(1, math.floor(shares*tp1_portion)))
            close(quantity, target_1, index, "TP1"); remaining -= quantity; tp1_hit=True
            if not remaining: break
        if remaining and target_2 is not None and high >= target_2: close(remaining, target_2, index, "TP2"); remaining=0; tp2_hit=True; break
    if remaining: close(remaining, float(data.iloc[last]["Close"]), last, "TIME")
    total = sum(leg["pnl"] for leg in legs)
    return {"entry_price": entry, "exit_index": legs[-1]["exit_index"], "exit_price": legs[-1]["exit_price"], "tp1_hit": tp1_hit, "tp2_hit": tp2_hit, "stop_hit": stop_hit, "holding_days": legs[-1]["exit_index"]-entry_index+1, "r_multiple": total/risk, "return_pct": total/(entry*shares)*100, "exit_legs": legs}


def _metrics(rows: list[dict], rejected=0) -> dict:
    if not rows: return {"total_trades":0,"rejected_trades":rejected,"expectancy":0,"profit_factor":None,"win_rate":0,"maximum_drawdown":0,"average_r":0,"trades_per_year":0,"average_holding_time":0,"expectancy_95_ci":None}
    values=np.array([row["r_multiple"] for row in rows]); gains,losses=values[values>0].sum(),-values[values<0].sum(); equity=np.cumsum(values); dd=equity-np.maximum.accumulate(np.maximum(equity,0)); rng=np.random.default_rng(RANDOM_SEED+len(rows)); means=values[rng.integers(0,len(values),size=(BOOTSTRAP_SAMPLES,len(values)))].mean(axis=1); years=max(1,(pd.Timestamp(rows[-1]["signal_date"])-pd.Timestamp(rows[0]["signal_date"])).days/365.25)
    return {"total_trades":len(rows),"rejected_trades":rejected,"expectancy":round(float(values.mean()),4),"profit_factor":round(float(gains/losses),4) if losses else None,"win_rate":round(float((values>0).mean()*100),2),"maximum_drawdown":round(float(dd.min()),4),"average_r":round(float(values.mean()),4),"trades_per_year":round(len(rows)/years,2),"average_holding_time":round(float(np.mean([row["holding_days"] for row in rows])),2),"expectancy_95_ci":[round(float(np.percentile(means,2.5)),4),round(float(np.percentile(means,97.5)),4)]}


def _group(rows, rejected, field):
    return {value:_metrics([row for row in rows if row[field]==value],sum(row[field]==value for row in rejected)) for value in sorted({row[field] for row in rows+rejected})}


def _run(config, candidates, histories):
    trades=[]; rejected=[]; active=defaultdict(lambda:-1)
    for candidate in sorted(candidates,key=lambda row:(row["ticker"],row["index"])):
        shared={key:value for key,value in candidate.items() if key!="index"}; shared.update(config)
        if candidate["index"]+1 <= active[candidate["ticker"]]: rejected.append({"record_type":"REJECTED",**shared,"reason":"Overlapping position for ticker"}); continue
        data=histories[candidate["ticker"]]; entry_index=next((idx for idx in range(candidate["index"]+1,candidate["index"]+config["entry_wait"]+1) if float(data.iloc[idx]["Low"])<=candidate["ema20"]<=float(data.iloc[idx]["High"])),None)
        if entry_index is None: rejected.append({"record_type":"REJECTED",**shared,"reason":"Pullback limit was not traded within entry window"}); continue
        entry=entry_fill_price(candidate["ema20"],SLIPPAGE_BPS*config["cost_multiplier"]); stop=candidate["swing_low_20"]-config["stop_atr"]*candidate["atr"]; risk=entry-stop
        if risk<=0 or risk/entry>MAX_RISK_PCT: rejected.append({"record_type":"REJECTED",**shared,"reason":"Position risk exceeds 5% of entry price"}); continue
        t1r,t2r,portion=TARGETS[config["target_profile"]]; t1,t2=entry+t1r*risk,entry+t2r*risk if t2r else None
        outcome=_simulate(data,entry_index,entry,stop,t1,t2,portion,SLIPPAGE_BPS*config["cost_multiplier"],TRANSACTION_COST_BPS*config["cost_multiplier"])
        if outcome is None: rejected.append({"record_type":"REJECTED",**shared,"reason":"Invalid executable trade"}); continue
        active[candidate["ticker"]]=outcome["exit_index"]
        trades.append({"record_type":"TRADE","trade_id":f"{config['config_id']}-{candidate['ticker']}-{candidate['signal_date']}",**shared,"entry_date":str(data.index[entry_index].date()),"entry_price":entry,"stop_loss":stop,"target_1":t1,"target_2":t2,"exit_date":str(data.index[outcome['exit_index']].date()),**outcome})
    return trades,rejected


def _configs():
    return [{"config_id":f"wait{wait}_stop{stop:g}_target{target}_cost{cost}x","entry_wait":wait,"stop_atr":stop,"target_profile":target,"cost_multiplier":cost} for wait in WAIT_WINDOWS for stop in STOP_ATRS for target in TARGETS for cost in COST_MULTIPLIERS]


def run_audit(provider=None):
    provider=provider or get_market_data_provider(); end=date.today()-timedelta(days=1); start=end-timedelta(days=5*365+15); benchmark,benchmark_error=_history(provider,"SPY",start,end); histories={}; failures={}
    if benchmark_error: failures["SPY"]=benchmark_error
    for ticker in SYMBOLS:
        data,error=_history(provider,ticker,start,end)
        if error: failures[ticker]=error
        else: histories[ticker]=data
    if benchmark is None or len(histories)<100: return {"audit_status":"blocked","validated_symbols":len(histories),"provider_failures":failures,"reason":"At least 100 validated five-year histories and SPY are required."}
    candidates=_candidates(histories,benchmark); results={}; ledger=[]
    for config in _configs():
        trades,rejected=_run(config,candidates,histories); results[config["config_id"]]={"parameters":config,"overall":_metrics(trades,len(rejected)),"by_sector":_group(trades,rejected,"sector"),"by_market_regime":_group(trades,rejected,"market_regime"),"by_walk_forward_period":_group(trades,rejected,"walk_forward_period"),"rejection_reasons":dict(sorted(Counter(row["reason"] for row in rejected).items()))}; ledger.extend(trades)
    baseline=results["wait3_stop1_targetr15_3_cost1x"]; qualifying=[]
    for config_id,result in results.items():
        overall,walks,sectors=result["overall"],result["by_walk_forward_period"],result["by_sector"]; double=results[config_id.replace("cost1x","cost2x")]["overall"] if "cost1x" in config_id else None; positive_walks=sum(value["expectancy"]>0 for value in walks.values()); profit=[max(0,value["expectancy"])*value["total_trades"] for value in sectors.values()]; concentration=max(profit)/sum(profit) if sum(profit) else 1
        # A strategy with a clearly negative, adequately sampled regime is not
        # production-robust even if it passes the aggregate gates.
        regime_safe=all(value["expectancy"]>=0 for value in result["by_market_regime"].values() if value["total_trades"]>=30)
        if overall["total_trades"]>=100 and positive_walks>=2 and double and (double["profit_factor"] or 0)>1 and concentration<=.5 and overall["maximum_drawdown"]>=-15 and regime_safe: qualifying.append(config_id)
    return {"audit_status":"completed","parameters":{"universe_size":len(histories),"start":start.isoformat(),"end":end.isoformat(),"signal_generation":"unchanged close-of-candle institutional analysis","entry":"signal-time EMA20 limit","risk_limit":"5% of entry","cost_interpretation":"slippage and transaction cost both multiplied","walk_forward":"three chronological equal signal-count periods","regime_definition":"Bull: SPY close and SMA50 above SMA200; Bear: both below; otherwise Sideways"},"provider_failures":failures,"candidate_signals":len(candidates),"configurations":results,"baseline_configuration":baseline,"production_recommendation":{"approved":bool(qualifying),"qualifying_configurations":qualifying,"decision":"No configuration meets every production-use gate." if not qualifying else "Only listed configurations meet every pre-defined gate."},"trades":ledger}


def write_artifacts(results):
    OUTPUT.mkdir(exist_ok=True); (OUTPUT/"pullback_robustness_results.json").write_text(json.dumps({key:value for key,value in results.items() if key!="trades"},indent=2)); rows=[]
    for trade in results.get("trades",[]):
        shared={key:value for key,value in trade.items() if key!="exit_legs"}
        for number,leg in enumerate(trade["exit_legs"],1): rows.append({**shared,"leg_number":number,**{f"leg_{key}":value for key,value in leg.items()}})
    with (OUTPUT/"pullback_robustness_trades.csv").open("w",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=sorted({key for row in rows for key in row}) if rows else ["ticker"],lineterminator="\n"); writer.writeheader(); writer.writerows(rows)


if __name__ == "__main__":
    result=run_audit(); write_artifacts(result); print(json.dumps({key:value for key,value in result.items() if key!="trades"},indent=2))

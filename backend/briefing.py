from engines.institutional_engine import calculate_institutional_analysis
from engines.engine_utils import has_valid_market_data, safe_float
from engines.trade_plan_engine import calculate_trade_plan
from atr import add_atr
from support_resistance import calculate_support_resistance


def _trend_label(score: int) -> str:
    return "Bullish" if score >= 70 else "Bearish" if score <= 40 else "Neutral"


def build_daily_briefing(watchlist: list[str], get_data) -> dict:
    """Create a public daily briefing from the existing institutional and plan engines."""

    benchmark = get_data("SPY", period="2y", interval="1d")
    opportunities = []
    moves = []

    for ticker in watchlist:
        data = get_data(ticker, period="2y", interval="1d")
        if data is None or not has_valid_market_data(data, minimum_rows=200):
            continue
        analysis = calculate_institutional_analysis(data, benchmark)
        enriched = add_atr(data)
        levels = calculate_support_resistance(enriched)
        atr = safe_float(enriched["ATR"].iloc[-1])
        plan = None
        if atr and atr > 0:
            try:
                plan = calculate_trade_plan(ticker, enriched, 10000, 1, {"confidence": analysis["overall_score"]}, levels["support"], levels["resistance"], atr)
            except ValueError:
                pass
        close = float(data["Close"].iloc[-1]); previous = float(data["Close"].iloc[-2])
        moves.append({"ticker": ticker, "change_percent": round(((close / previous) - 1) * 100, 2)})
        opportunities.append({"ticker": ticker, "confidence": analysis["overall_score"], "recommendation": analysis["recommendation"], "rr": plan["risk_reward_target_1"] if plan else 0, "trend": _trend_label(analysis["engines"]["trend"]["score"]), "price": round(close, 2)})

    opportunities.sort(key=lambda item: item["confidence"], reverse=True)
    buy_signals = [item["ticker"] for item in opportunities if item["recommendation"] == "BUY"]
    strong_buys = [item["ticker"] for item in opportunities if item["recommendation"] == "STRONG BUY"]
    strongest = opportunities[0]["ticker"] if opportunities else "the watchlist"
    high_quality = sum(1 for item in opportunities if item["confidence"] >= 65 and item["rr"] >= 1.5)

    def index_health(ticker):
        data = get_data(ticker, period="1y", interval="1d")
        if data is None or not has_valid_market_data(data, minimum_rows=50): return {"label": "Unavailable", "value": "—"}
        close = float(data["Close"].iloc[-1]); ema50 = data["Close"].ewm(span=50, adjust=False).mean().iloc[-1]
        return {"label": "Bullish" if close > ema50 else "Bearish", "value": f"${close:.2f}"}

    spy = index_health("SPY"); nasdaq = index_health("QQQ"); vix = index_health("^VIX")
    market_regime = "Risk-on" if spy["label"] == "Bullish" and nasdaq["label"] == "Bullish" else "Mixed"
    return {"market_summary": {"sentiment": "Bullish" if market_regime == "Risk-on" else "Neutral", "confidence": opportunities[0]["confidence"] if opportunities else 50, "explanation": f"{market_regime} conditions favor selective, high-confidence setups."}, "opportunities": opportunities[:10], "watchlist_summary": {"biggest_winner": max(moves, key=lambda item: item["change_percent"], default=None), "biggest_loser": min(moves, key=lambda item: item["change_percent"], default=None), "new_buy_signals": buy_signals, "new_strong_buy_signals": strong_buys}, "market_health": {"sp_trend": spy, "nasdaq_trend": nasdaq, "vix": vix, "fear_greed": {"label": "Placeholder", "value": "API pending"}, "market_regime": {"label": market_regime, "value": "Institutional regime"}}, "daily_opportunities": f"Today I found {high_quality} high-quality setups. The strongest opportunity is {strongest}. Technology remains the strongest sector. Avoid weak semiconductor names with low relative strength.", "upcoming_events": [{"title": "Earnings", "detail": "Earnings calendar placeholder"}, {"title": "Economic calendar", "detail": "Macro events placeholder"}, {"title": "Fed meetings", "detail": "Federal Reserve schedule placeholder"}]}

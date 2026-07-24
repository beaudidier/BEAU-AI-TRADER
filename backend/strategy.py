from config import BUY_SCORE, WATCH_SCORE


def analyse(df):
    """
    Analyseert de laatste candle en geeft een score + aanbeveling.
    """

    current = df.iloc[-1]

    score = 0

    # Trend
    if current["EMA20"] > current["EMA50"]:
        score += 5

    # Prijs boven EMA20
    if current["Close"] > current["EMA20"]:
        score += 2

    # Momentum
    if current["RSI"] > 50:
        score += 2

    # Laatste candle hoger dan vorige
    if current["Close"] > df["Close"].iloc[-2]:
        score += 1

    # Advies
    if score >= BUY_SCORE:
        recommendation = "🟢 BUY"

    elif score >= WATCH_SCORE:
        recommendation = "🟡 WATCH"

    else:
        recommendation = "🔴 SKIP"

    return {
        "ticker": "",
        "price": round(float(current["Close"]), 2),
        "ema20": round(float(current["EMA20"]), 2),
        "ema50": round(float(current["EMA50"]), 2),
        "rsi": round(float(current["RSI"]), 2),
        "score": score,
        "recommendation": recommendation,
    }
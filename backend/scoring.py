from support_resistance import calculate_support_resistance
from volume import get_volume_score
from decision_rules import recommendation_for_score


def calculate_score(df):
    """
    Berekent een score van 0 t/m 100.
    """

    current = df.iloc[-1]

    score = 0
    reasons = []

    # Trend (30 punten)
    if current["EMA20"] > current["EMA50"]:
        score += 30
        reasons.append("EMA20 boven EMA50")

    # Prijs boven EMA20 (15 punten)
    if current["Close"] > current["EMA20"]:
        score += 15
        reasons.append("Prijs boven EMA20")

    # RSI (15 punten)
    if 55 <= current["RSI"] <= 70:
        score += 15
        reasons.append("Gezonde RSI")

    elif current["RSI"] > 50:
        score += 10
        reasons.append("Positieve RSI")

    # Momentum (10 punten)
    if current["Close"] > df["Close"].iloc[-2]:
        score += 10
        reasons.append("Bullish candle")

    # Volume (10 punten)
    volume_score = get_volume_score(df)

    score += volume_score

    if volume_score:
        reasons.append("Hoog volume")

    # Support / Resistance (20 punten)
    sr = calculate_support_resistance(df)

    support = sr["support"]
    resistance = sr["resistance"]

    upside = resistance - float(current["Close"])
    downside = float(current["Close"]) - support

    if downside > 0:

        rr = upside / downside

        if rr >= 3:
            score += 20
            reasons.append("Risk/Reward > 3")

        elif rr >= 2:
            score += 15
            reasons.append("Risk/Reward > 2")

        elif rr >= 1.5:
            score += 10
            reasons.append("Risk/Reward > 1.5")

    recommendation = recommendation_for_score(score)

    return {
        "score": score,
        "recommendation": recommendation,
        "support": support,
        "resistance": resistance,
        "reasons": reasons,
    }

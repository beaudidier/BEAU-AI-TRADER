from config import WATCHLIST

from data import get_stock_data
from indicators import add_indicators
from atr import add_atr
from volume import add_volume_analysis
from scoring import calculate_score


def print_header():
    print("\n" + "=" * 90)
    print("🚀 BEAU AI TRADER v0.2")
    print("=" * 90)


def print_stock(result):

    print(f"\n{result['ticker']}")
    print("-" * 60)

    print(f"Prijs          : ${result['price']:.2f}")
    print(f"EMA20          : {result['ema20']:.2f}")
    print(f"EMA50          : {result['ema50']:.2f}")
    print(f"RSI            : {result['rsi']:.2f}")
    print(f"ATR            : {result['atr']:.2f}")

    print(f"\nSupport        : ${result['support']:.2f}")
    print(f"Resistance     : ${result['resistance']:.2f}")

    print(f"\nScore          : {result['score']}/100")
    print(f"Advies         : {result['recommendation']}")

    print("\nWaarom?")

    for reason in result["reasons"]:
        print(f"  ✓ {reason}")


def main():

    print_header()

    results = []

    for ticker in WATCHLIST:

        print(f"\nScannen: {ticker}")

        df = get_stock_data(ticker)

        if df is None:
            print("Geen data.")
            continue

        df = add_indicators(df)
        df = add_atr(df)
        df = add_volume_analysis(df)

        score = calculate_score(df)

        current = df.iloc[-1]

        results.append({
            "ticker": ticker,
            "price": float(current["Close"]),
            "ema20": float(current["EMA20"]),
            "ema50": float(current["EMA50"]),
            "rsi": float(current["RSI"]),
            "atr": float(current["ATR"]),
            "support": score["support"],
            "resistance": score["resistance"],
            "score": score["score"],
            "recommendation": score["recommendation"],
            "reasons": score["reasons"],
        })

    results.sort(key=lambda x: x["score"], reverse=True)

    print("\n")
    print("=" * 90)
    print("🏆 BESTE SETUPS")
    print("=" * 90)

    for result in results:
        print_stock(result)

    print("\n✅ Scan voltooid.")


if __name__ == "__main__":
    main()
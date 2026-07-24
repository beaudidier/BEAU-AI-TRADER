from config import WATCHLIST

from .universe_provider import UniverseProvider


# Development-safe constituent snapshots. They are intentionally local so scans
# never depend on a paid index-membership API.
SP500 = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "BRK-B", "AVGO", "TSLA", "LLY", "JPM", "V", "UNH", "XOM", "MA", "COST", "PG", "JNJ", "HD", "MRK", "ABBV", "CVX", "KO", "PEP", "ADBE", "CRM", "WMT", "BAC", "NFLX", "AMD", "CSCO", "TMO", "ACN", "MCD", "LIN", "ABT", "DHR", "ORCL", "QCOM", "TXN", "PM", "IBM", "AMGN", "GE", "CAT", "INTU", "NOW", "ISRG", "GS", "SPGI"]
NASDAQ100 = ["NVDA", "MSFT", "AAPL", "AMZN", "META", "AVGO", "GOOGL", "GOOG", "TSLA", "COST", "NFLX", "AMD", "ADBE", "PEP", "CSCO", "TMUS", "INTC", "CMCSA", "INTU", "QCOM", "AMGN", "TXN", "HON", "AMAT", "BKNG", "SBUX", "VRTX", "PANW", "ADP", "GILD"]
DOW30 = ["AAPL", "AMGN", "AMZN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS", "GS", "HD", "HON", "IBM", "INTC", "JNJ", "JPM", "KO", "MCD", "MMM", "MRK", "MSFT", "NKE", "NVDA", "PG", "SHW", "TRV", "UNH", "V", "WMT"]


class StockUniverseProvider(UniverseProvider):
    market = "stocks"

    def supported_universes(self) -> set[str]:
        return {"demo", "sp500", "nasdaq100", "dow30", "custom", "all_us"}

    def symbols(self, universe: str, custom_symbols: list[str] | None = None) -> list[str]:
        selections = {"demo": WATCHLIST, "sp500": SP500, "nasdaq100": NASDAQ100, "dow30": DOW30}
        if universe == "custom":
            return _unique(custom_symbols or [])
        if universe == "all_us":
            return _unique([*SP500, *NASDAQ100, *DOW30])
        return _unique(selections.get(universe, []))


def _unique(symbols: list[str]) -> list[str]:
    return list(dict.fromkeys(symbol.strip().upper() for symbol in symbols if symbol and symbol.strip()))

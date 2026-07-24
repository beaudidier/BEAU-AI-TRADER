from .universe_provider import UniverseProvider


# Yahoo Finance cryptocurrency symbols, ordered as a stable development snapshot.
TOP100 = [f"{symbol}-USD" for symbol in ["BTC", "ETH", "USDT", "BNB", "SOL", "USDC", "XRP", "DOGE", "ADA", "TRX", "AVAX", "TON", "SHIB", "DOT", "LINK", "BCH", "MATIC", "LTC", "NEAR", "UNI", "ICP", "APT", "DAI", "FIL", "ATOM", "XLM", "ETC", "HBAR", "CRO", "MKR", "ARB", "VET", "OP", "INJ", "GRT", "ALGO", "QNT", "AAVE", "SAND", "MANA", "EGLD", "XTZ", "THETA", "AXS", "FLOW", "EOS", "KAVA", "RUNE", "SNX", "CHZ", "KSM", "LDO", "CRV", "COMP", "ENJ", "ZEC", "DASH", "BAT", "1INCH", "KNC", "YFI", "WAVES", "ZIL", "CELO", "ANKR", "ICX", "FTM", "MINA", "ROSE", "OCEAN", "SUSHI", "GLM", "SKL", "BAL", "STORJ", "AUDIO", "UMA", "BAND", "API3", "COTI", "LRC", "OMG", "REN", "SC", "ZEN", "QTUM", "ONT", "IOST", "DENT", "AR", "KDA", "GMX", "DYDX", "JASMY", "FLUX", "MASK", "STX", "KAS", "WLD", "PEPE", "BONK", "FLOKI"]]


class CryptoUniverseProvider(UniverseProvider):
    market = "crypto"

    def supported_universes(self) -> set[str]:
        return {"top50", "top100", "custom"}

    def symbols(self, universe: str, custom_symbols: list[str] | None = None) -> list[str]:
        if universe == "custom":
            return list(dict.fromkeys(_crypto_symbol(symbol) for symbol in custom_symbols or [] if symbol and symbol.strip()))
        if universe == "top50":
            return TOP100[:50]
        return TOP100.copy() if universe == "top100" else []


def _crypto_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    return normalized if normalized.endswith("-USD") else f"{normalized}-USD"

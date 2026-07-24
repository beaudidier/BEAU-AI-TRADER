"""
BEAU AI TRADER
Version: 0.1

Configuratiebestand.
Hier pas je straks eenvoudig de instellingen van de scanner aan.
"""

# Aandelen die worden gescand
WATCHLIST = [
    "MU",
    "NVDA",
    "AMD",
    "TSLA",
    "AAPL",
    "MSFT",
    "META",
    "AMZN",
    "GOOGL",
    "PLTR",
]

# Hoeveel historische data ophalen
PERIOD = "6mo"

# Candles
INTERVAL = "1d"

# Indicator instellingen
EMA_FAST = 20
EMA_SLOW = 50
RSI_PERIOD = 14

# Score grenzen
BUY_SCORE = 8
WATCH_SCORE = 6
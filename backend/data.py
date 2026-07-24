from config import PERIOD, INTERVAL
from providers import get_market_data_provider


def get_stock_data(ticker, period=PERIOD, interval=INTERVAL, start=None, end=None):
    """
    Download historical price data through the configured market-data provider.
    """

    return get_market_data_provider().get_history(ticker, period=period, interval=interval, start=start, end=end)

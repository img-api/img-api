import requests_cache
import yfinance as yf
import pandas as pd

from datetime import timedelta

from requests import Session
from requests_cache import CacheMixin, SQLiteCache
from requests_ratelimiter import LimiterMixin, MemoryQueueBucket
from pyrate_limiter import Duration, RequestRate, Limiter


class CachedLimiterSession(CacheMixin, LimiterMixin, Session):
    pass


# Fetching current stock data
#request_session = requests_cache.CachedSession('yfinance_cache', expire_after=timedelta(hours=24))

request_session = CachedLimiterSession(
    limiter=Limiter(RequestRate(2, Duration.SECOND * 5)),  # max 2 requests per 5 seconds
    bucket_class=MemoryQueueBucket,
    backend=SQLiteCache("yfinance.cache"),
)

def fetch_all_tickers_symbols():
    # Read and print the stock tickers that make up S&P500
    sp500 = pd.read_html(
        'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')[0]
    print(sp500.head())
    sp500_tickers = sp500['Symbol'].tolist()

    nasdaq_100 = pd.read_html('https://en.wikipedia.org/wiki/NASDAQ-100')[4]
    nasdaq_100_tickers = nasdaq_100['Ticker'].tolist()

    return sp500_tickers


def fetch_tickers_info(ticker):
    global request_session
    ticker_info = yf.Ticker(ticker, session=request_session)
    return ticker_info


def ticker_dump_data(tickers, data):
    for ticker in tickers:
        print(f"Ticker: {ticker}")
        for index, row in data[ticker].iterrows():
            print(
                f"Time: {index}, Open: {row['Open']}, High: {row['High']}, Low: {row['Low']}, Close: {row['Close']}, Volume: {row['Volume']}"
            )

        print("\n")

    latest_prices = {ticker: data[ticker]['Close'][-1] for ticker in tickers}
    for ticker, price in latest_prices.items():
        print(f"{ticker}: ${price:.2f}")

    return data


def fetch_tickers_list(tickers, period='1d', interval='1m'):
    global request_session

    # Monkey-patch yfinance to use the cached session
    yf.utils.requests = request_session
    data = yf.download(tickers, period=period, interval=interval, group_by='ticker', prepost=True)

    return data

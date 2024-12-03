import yfinance as yf
from pyrate_limiter import Duration, Limiter, RequestRate
from requests import Session
from requests_cache import CacheMixin, SQLiteCache
from requests_ratelimiter import LimiterMixin, MemoryQueueBucket


class CachedLimiterSession(CacheMixin, LimiterMixin, Session):
    pass


# Fetching current stock data
#request_session = requests_cache.CachedSession('yfinance_cache', expire_after=timedelta(hours=24))

request_session = CachedLimiterSession(
    limiter=Limiter(RequestRate(2, Duration.SECOND * 5)),  # max 2 requests per 5 seconds
    bucket_class=MemoryQueueBucket,
    backend=SQLiteCache("yfinance.cache"),
)

def fetch_tickers_info(ticker, no_cache=False):
    global request_session

    if no_cache:
        ticker_info = yf.Ticker(ticker)
    else:
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

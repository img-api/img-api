import os
import re
from urllib.parse import urlparse

from api.print_helper import *

""" CHATGPT
Common Exchanges and URL Patterns
NYSE (New York Stock Exchange)

URL Pattern: https://www.nyse.com/quote/EXCHANGE:TICKER
Example URL: https://www.nyse.com/quote/XNYS:AZO
NASDAQ (National Association of Securities Dealers Automated Quotations)

URL Pattern: https://www.nasdaq.com/market-activity/stocks/TICKER
Example URL: https://www.nasdaq.com/market-activity/stocks/cinf
CBOE (Chicago Board Options Exchange)

URL Pattern: https://markets.cboe.com/us/equities/listings/listed_products/symbols/TICKER
Example URL: https://markets.cboe.com/us/equities/listings/listed_products/symbols/CBOE
AMEX (American Stock Exchange)

URL Pattern: https://www.nyse.com/quote/EXCHANGE:TICKER (similar to NYSE)
Example URL: https://www.nyse.com/quote/XASE:SPY
OTC (Over The Counter Markets)

URL Pattern: https://www.otcmarkets.com/stock/TICKER/quote
Example URL: https://www.otcmarkets.com/stock/TSNP/quote
London Stock Exchange (LSE)

URL Pattern: https://www.londonstockexchange.com/stock/TICKER/company-page
Example URL: https://www.londonstockexchange.com/stock/HSBA/company-page
Tokyo Stock Exchange (TSE)

URL Pattern: https://www.jpx.co.jp/english/listing/stocks/TICKER.html
Example URL: https://www.jpx.co.jp/english/listing/stocks/7203.html
Toronto Stock Exchange (TSX)

URL Pattern: https://www.tsx.com/company-directory/listed-companies/TICKER
Example URL: https://www.tsx.com/company-directory/listed-companies/AAPL

"""

def extract_exchange_ticker_from_url(url):
    """
    Extracts the exchange and ticker symbol from a given URL.

    Parameters:
        url (str): The URL containing exchange and ticker information.

    Returns:
        tuple: A tuple containing the exchange and ticker symbol.
               Returns (None, None) if not found.
    """
    # Parse the URL to extract the path
    parsed_url = urlparse(url)
    path = parsed_url.path

    # Dictionary to map URL patterns to exchanges
    url_patterns = {
        'NYSE': r'/quote/([A-Z]+):([A-Z]+)',
        'NASDAQ': r'/market-activity/stocks/([a-z]+)',
        'CBOE': r'/symbols/([A-Z]+)',
        'AMEX': r'/quote/([A-Z]+):([A-Z]+)',
        'OTC': r'/stock/([A-Z]+)/quote',
        'LSE': r'/stock/([A-Z]+)/company-page',
        'TSE': r'/english/listing/stocks/(\d+).html',
        'TSX': r'/company-directory/listed-companies/([A-Z]+)'
    }

    # Loop through each pattern to find a match
    for exchange, pattern in url_patterns.items():
        match = re.search(pattern, path)
        if match:
            if exchange in ['NYSE', 'AMEX']:
                # Extract exchange and ticker for NYSE and AMEX
                return match.groups()
            elif exchange in ['NASDAQ', 'CBOE', 'OTC', 'LSE', 'TSX']:
                # NASDAQ, CBOE, OTC, LSE, TSX extract only the ticker
                ticker = match.group(1).upper()
                return exchange, ticker
            elif exchange == 'TSE':
                # TSE has a numeric ticker
                ticker = match.group(1)
                return exchange, ticker

    # If no pattern matches, return None
    return None, None


def tickers_unit_test():
    # Test cases
    urls = [
        "https://www.nyse.com/quote/XNYS:AZO",
        "https://markets.cboe.com/us/equities/listings/listed_products/symbols/CBOE",
        "https://www.nasdaq.com/market-activity/stocks/cinf", "https://www.otcmarkets.com/stock/TSNP/quote",
        "https://www.londonstockexchange.com/stock/HSBA/company-page",
        "https://www.jpx.co.jp/english/listing/stocks/7203.html",
        "https://www.tsx.com/company-directory/listed-companies/AAPL"
    ]

    for url in urls:
        exchange, ticker = extract_exchange_ticker_from_url(url)
        print(f"URL: {url} -> Exchange: {exchange}, Ticker: {ticker}")

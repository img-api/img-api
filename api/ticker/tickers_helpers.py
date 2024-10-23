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

mic_to_exchange = {
    'XNYS': {
        'full_name': 'New York Stock Exchange',
        'abbreviation': 'NYSE',
        'location': 'New York, USA'
    },
    'XNAS': {
        'full_name': 'Nasdaq Stock Market',
        'abbreviation': 'NASDAQ',
        'location': 'New York, USA'
    },
    'XLON': {
        'full_name': 'London Stock Exchange',
        'abbreviation': 'LSE',
        'location': 'London, UK'
    },
    'XTKS': {
        'full_name': 'Tokyo Stock Exchange',
        'abbreviation': 'TSE',
        'location': 'Tokyo, Japan'
    },
    'XHKG': {
        'full_name': 'Hong Kong Stock Exchange',
        'abbreviation': 'HKEX',
        'location': 'Hong Kong, China'
    },
    'XSHG': {
        'full_name': 'Shanghai Stock Exchange',
        'abbreviation': 'SSE',
        'location': 'Shanghai, China'
    },
    'XSHE': {
        'full_name': 'Shenzhen Stock Exchange',
        'abbreviation': 'SZSE',
        'location': 'Shenzhen, China'
    },
    'XTSE': {
        'full_name': 'Toronto Stock Exchange',
        'abbreviation': 'TSX',
        'location': 'Toronto, Canada'
    },
    'XETR': {
        'full_name': 'Deutsche Börse Xetra',
        'abbreviation': 'Xetra',
        'location': 'Frankfurt, Germany'
    },
    'XFRA': {
        'full_name': 'Frankfurt Stock Exchange',
        'abbreviation': 'Frankfurt',
        'location': 'Frankfurt, Germany'
    },
    'XASX': {
        'full_name': 'Australian Securities Exchange',
        'abbreviation': 'ASX',
        'location': 'Sydney, Australia'
    },
    'XMIL': {
        'full_name': 'Borsa Italiana',
        'abbreviation': 'Milan',
        'location': 'Milan, Italy'
    },
    'XNSE': {
        'full_name': 'National Stock Exchange of India',
        'abbreviation': 'NSE',
        'location': 'Mumbai, India'
    },
    'XBOM': {
        'full_name': 'Bombay Stock Exchange',
        'abbreviation': 'BSE',
        'location': 'Mumbai, India'
    },
    'XSWX': {
        'full_name': 'SIX Swiss Exchange',
        'abbreviation': 'SIX',
        'location': 'Zurich, Switzerland'
    },
    'XJSE': {
        'full_name': 'Johannesburg Stock Exchange',
        'abbreviation': 'JSE',
        'location': 'Johannesburg, South Africa'
    },
    'XMEX': {
        'full_name': 'Mexican Stock Exchange',
        'abbreviation': 'BMV',
        'location': 'Mexico City, Mexico'
    },
    'XMOS': {
        'full_name': 'Moscow Exchange',
        'abbreviation': 'MOEX',
        'location': 'Moscow, Russia'
    },
    'XKRX': {
        'full_name': 'Korea Exchange',
        'abbreviation': 'KRX',
        'location': 'Seoul, South Korea'
    },
    'BVMF': {
        'full_name': 'B3 - Brasil Bolsa Balcão',
        'abbreviation': 'B3',
        'location': 'Sao Paulo, Brazil'
    },
    'XPAR': {
        'full_name': 'Euronext Paris',
        'abbreviation': 'Paris',
        'location': 'Paris, France'
    },
    'XAMS': {
        'full_name': 'Euronext Amsterdam',
        'abbreviation': 'Amsterdam',
        'location': 'Amsterdam, Netherlands'
    },
    'XNYS': {
        'full_name': 'New York Stock Exchange',
        'abbreviation': 'NYSE',
        'location': 'New York, USA'
    },
    'XNYS': {
        'full_name': 'New York Stock Exchange',
        'abbreviation': 'NYSE',
        'location': 'New York, USA'
    },
    'XSGO': {
        'full_name': 'Santiago Stock Exchange',
        'abbreviation': 'BCS',
        'location': 'Santiago, Chile'
    },
    'XOSL': {
        'full_name': 'Oslo Stock Exchange',
        'abbreviation': 'OSE',
        'location': 'Oslo, Norway'
    },
    'XBRU': {
        'full_name': 'Euronext Brussels',
        'abbreviation': 'Brussels',
        'location': 'Brussels, Belgium'
    },
    'XBUD': {
        'full_name': 'Budapest Stock Exchange',
        'abbreviation': 'BSE',
        'location': 'Budapest, Hungary'
    },
    'XICE': {
        'full_name': 'Nasdaq Iceland',
        'abbreviation': 'ICE',
        'location': 'Reykjavik, Iceland'
    },
    'XCSE': {
        'full_name': 'Nasdaq Copenhagen',
        'abbreviation': 'CPH',
        'location': 'Copenhagen, Denmark'
    },
    'XHEL': {
        'full_name': 'Nasdaq Helsinki',
        'abbreviation': 'HEL',
        'location': 'Helsinki, Finland'
    },
    'XSTO': {
        'full_name': 'Nasdaq Stockholm',
        'abbreviation': 'STO',
        'location': 'Stockholm, Sweden'
    }
}

# Comprehensive mapping of suffixes and prefixes to their standard exchange names
suffix_to_exchange = {
    '.AX': 'ASX',  # Australian Securities Exchange
    '.TO': 'TSX',  # Toronto Stock Exchange
    '.L': 'LON',  # London Stock Exchange
    '.HK': 'HKG',  # Hong Kong Stock Exchange
    '.SW': 'SIX',  # SIX Swiss Exchange
    '.F': 'FRA',  # Frankfurt Stock Exchange
    '.HE': 'HEL',  # Nasdaq Helsinki
    '.ST': 'STO',  # Nasdaq Stockholm
    '.CO': 'CPH',  # Nasdaq Copenhagen
    '.OL': 'OSL',  # Oslo Børs
    '.IS': 'ISE',  # Euronext Dublin
    '.PA': 'EPA',  # Euronext Paris
    '.AS': 'AMS',  # Euronext Amsterdam
    '.MI': 'MIL',  # Borsa Italiana (Milan)
    '.VX': 'VTX',  # SIX Swiss Exchange
    '.JK': 'IDX',  # Indonesia Stock Exchange
    '.KQ': 'KOSDAQ',  # Korea Securities Dealers Automated Quotations
    '.KS': 'KRX',  # Korea Exchange
    '.SI': 'SGX',  # Singapore Exchange
    '.T': 'TSE',  # Tokyo Stock Exchange
    '.NZ': 'NZX',  # New Zealand Exchange
    '.SA': 'BVMF',  # B3 - Brasil Bolsa Balcão (Sao Paulo)
    '.MC': 'BME',  # Bolsa de Madrid (Madrid Stock Exchange)
    '.BR': 'EBR',  # Euronext Brussels
    '.VN': 'VSE',  # Vienna Stock Exchange
    '.WA': 'WSE'  # Warsaw Stock Exchange
}

exchange_to_suffix = {v: k for k, v in suffix_to_exchange.items()}

prefix_to_exchange = {
    'NASDAQ': 'NASDAQ',  # Nasdaq Stock Market
    'NYQ': 'NYSE',  # New York Stock Exchange
    'NYE': 'NYSE',  # New York Stock Exchange
    'NYSE': 'NYSE',  # New York Stock Exchange
    'TYO': 'TSE',  # Tokyo Stock Exchange
    'OTCMKTS': 'OTC',  # OTC Markets
}

def extract_ticker_from_symbol(full_symbol):
    if ":" in full_symbol:
        exchange, stock = full_symbol.split(':')
        return stock

    if "." in full_symbol:
        stock, exchange = full_symbol.split('.')
        return stock

    return full_symbol

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


def get_exchange_verbose(exchange_name):
    verbose_map = {
        'AX': 'Australian Securities Exchange',  # ASX
        'TO': 'Toronto Stock Exchange',  # TSX
        'L': 'London Stock Exchange',  # LON
        'HK': 'Hong Kong Stock Exchange',  # HKG
        'SW': 'SIX Swiss Exchange',  # SIX
        'F': 'Frankfurt Stock Exchange',  # FRA
        'HE': 'Nasdaq Helsinki',  # HEL
        'ST': 'Nasdaq Stockholm',  # STO
        'CO': 'Nasdaq Copenhagen',  # CPH
        'OL': 'Oslo Børs',  # OSL
        'IS': 'Euronext Dublin',  # ISE
        'PA': 'Euronext Paris',  # EPA
        'AS': 'Euronext Amsterdam',  # AMS
        'MI': 'Borsa Italiana (Milan)',  # MIL
        'VX': 'SIX Swiss Exchange',  # VTX
        'JK': 'Indonesia Stock Exchange',  # IDX
        'KQ': 'Korea Securities Dealers Automated Quotations',  # KOSDAQ
        'KS': 'Korea Exchange',  # KRX
        'SI': 'Singapore Exchange',  # SGX
        'T': 'Tokyo Stock Exchange',  # TSE
        'NZ': 'New Zealand Exchange',  # NZX
        'SA': 'B3 - Brasil Bolsa Balcão (Sao Paulo)',  # BVMF
        'MC': 'Bolsa de Madrid (Madrid Stock Exchange)',  # BME
        'BR': 'Euronext Brussels',  # EBR
        'VN': 'Vienna Stock Exchange',  # VSE
        'WA': 'Warsaw Stock Exchange',  # WSE
        'NASDAQ': 'Nasdaq Stock Market',  # NASDAQ
        'NYQ': 'New York Stock Exchange',  # NYSE
        'NYE': 'New York Stock Exchange',  # NYSE
        'NYSE': 'New York Stock Exchange',  # NYSE
        'AMEX': 'NYSE American (formerly AMEX)',  # AMEX
        'TSX': 'Toronto Stock Exchange',  # TSX
        'TSXV': 'TSX Venture Exchange',  # TSXV
        'CSE': 'Canadian Securities Exchange',  # CSE
        'NEO': 'Cboe Canada',  # NEO
        'LON': 'London Stock Exchange',  # LON
        'EPA': 'Euronext Paris',  # EPA
        'AMS': 'Euronext Amsterdam',  # AMS
        'ETR': 'Deutsche Börse Xetra',  # ETR
        'STO': 'Nasdaq Stockholm',  # STO
        'ASX': 'Australian Securities Exchange',  # ASX
        'HKG': 'Hong Kong Stock Exchange',  # HKG
        'TYO': 'Tokyo Stock Exchange',  # TSE
        'OSL': 'Oslo Børs',  # OSL
        'CPH': 'Nasdaq Copenhagen',  # CPH
        'HEL': 'Nasdaq Helsinki',  # HEL
        'ISE': 'Euronext Dublin',  # ISE
        'BME': 'Bolsa de Madrid (Madrid Stock Exchange)',  # BME
        'FRA': 'Frankfurt Stock Exchange',  # FRA
        'SIX': 'SIX Swiss Exchange',  # SIX
        'VTX': 'SIX Swiss Exchange',  # VTX
        'IDX': 'Indonesia Stock Exchange',  # IDX
        'KOSDAQ': 'Korea Securities Dealers Automated Quotations',  # KOSDAQ
        'KRX': 'Korea Exchange',  # KRX
        'SGX': 'Singapore Exchange',  # SGX
        'NZX': 'New Zealand Exchange',  # NZX
        'BVMF': 'B3 - Brasil Bolsa Balcão (Sao Paulo)',  # BVMF
        'EBR': 'Euronext Brussels',  # EBR
        'VSE': 'Vienna Stock Exchange',  # VSE
        'WSE': 'Warsaw Stock Exchange',  # WSE
        'OTCMKTS': 'OTC Markets'  # OTC
    }

    # Check if exchange_name is in the prefix_to_exchange dictionary
    if exchange_name in verbose_map:
        return verbose_map[exchange_name]

    # If no match is found, return None or handle the case accordingly
    return exchange_name


def split_full_symbol(full_symbol: str) -> str:
    exchange, stock = full_symbol.split(':')
    return exchange, stock


def standardize_exchange_format(exchange: str) -> str:
    if not exchange:
        return ""

    if exchange not in mic_to_exchange:
        return exchange

    ex = mic_to_exchange[exchange]
    new_exchange = ex['abbreviation']
    print_b(ex['full_name'] + " MIC " + exchange + " => " + new_exchange)
    return new_exchange


def standardize_ticker_format(ticker: str) -> str:

    # Remove extension to symbol like PBR-A or PBR-B
    if "-" in ticker:
        full_symbol, end = ticker.split('-')

    # Case 1: Handle "EXCHANGE:TICKER" format

    if ':' in ticker:
        exchange, stock = ticker.split(':')

        if exchange in mic_to_exchange:
            exchange = standardize_exchange_format(exchange)
        else:
            # Standardize the exchange name using the prefix mapping
            exchange = prefix_to_exchange.get(exchange, exchange)  # Default to exchange itself if not found

        return f"{exchange}:{stock}"

    # Case 2: Handle "TICKER.SUFFIX" format
    elif '.' in ticker:
        stock, suffix = ticker.split('.')
        exchange = suffix_to_exchange.get(f'.{suffix}', suffix)  # Default to suffix itself if not found
        return f"{exchange}:{stock}"

    # Case 3: Handle "TICKER" format with no exchange (assume NASDAQ or other default logic)
    else:
        # Here we assume a default exchange if none is provided, let's assume NASDAQ
        return f"NASDAQ:{ticker}"


.

# Test cases


def tickers_unit_test():
    # Test cases
    ret = {}

    urls = [
        ("XNYS:AZO", "https://www.nyse.com/quote/XNYS:AZO"),
        ("CBOE:CBOE", "https://markets.cboe.com/us/equities/listings/listed_products/symbols/CBOE"),
        ("NASDAQ:CINF", "https://www.nasdaq.com/market-activity/stocks/cinf"),
        ("OTC:TSNP", "https://www.otcmarkets.com/stock/TSNP/quote"),
        ("LSE:HSBA", "https://www.londonstockexchange.com/stock/HSBA/company-page"),
        ("TSE:7203", "https://www.jpx.co.jp/english/listing/stocks/7203.html"),
        ("TSX:AAPL", "https://www.tsx.com/company-directory/listed-companies/AAPL"),
    ]

    for expected, url in urls:
        exchange, ticker = extract_exchange_ticker_from_url(url)
        st = exchange + ":" + ticker
        if not expected == st:
            ret[expected] = st
            print_r(f"URL: {url} -> Exchange: {exchange}, Ticker: {ticker}")
        else:
            print_b(f"URL: {url} -> Exchange: {exchange}, Ticker: {ticker}")

    test_cases = [("DYL.AX", "ASX:DYL"), ("NYQ:XXX", "NYSE:XXX"), ("NASDAQ:INTC", "NASDAQ:INTC"),
                  ("NYE:XXX", "NYSE:XXX"), ("INTC", "NASDAQ:INTC"), ("AAPL", "NASDAQ:AAPL"), ("GOOGL", "NASDAQ:GOOGL"),
                  ("2330.T", "TSE:2330"), ("005930.KS", "KRX:005930")]

    # Test the standardization function with ticker formats
    for ticker, expected in test_cases:
        result = standardize_ticker_format(ticker)

        if not result == expected:
            ret[expected] = result
            print_r(f"Test: {ticker} -> Expected: {expected}, Got: {result}, Passed: {result == expected}")
        else:
            print_b(f"Test: {ticker} -> Expected: {expected}, Got: {result}, Passed: {result == expected}")

    # Reverse so if we give ASX:DYL we get DYL.AX
    test_cases = [("DYL.AX", "ASX:DYL"), ("NASDAQ:INTC", "INTC"), ("XXX", "NYSE:XXX"), ("2330.T", "TSE:2330"),
                  ("005930.KS", "KRX:005930")]

    for expected, ticker in test_cases:
        result = standardize_ticker_format_to_yfinance(ticker)

        if not result == expected:
            ret[expected] = result
            print_r(f"Test: {ticker} -> Expected: {expected}, Got: {result}, Passed: {result == expected}")
        else:
            print_b(f"Test: {ticker} -> Expected: {expected}, Got: {result}, Passed: {result == expected}")

    return {"FAILED": ret}

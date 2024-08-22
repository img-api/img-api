import os
import requests_cache
import yfinance as yf
import pandas as pd

from datetime import timedelta


def get_data(url, cache_file, index):
    if os.path.exists(cache_file):
        # Load from cache
        return pd.read_pickle(cache_file)
    else:
        # Fetch data
        df = pd.read_html(url)[index]
        df.to_pickle(cache_file)  # Save to cache
        return df


def get_all_tickers_and_symbols():

    sp500 = get_data('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', "sp_500_companies.pkl", 0)
    sp500_tickers = sp500['Symbol'].tolist()

    nasdaq_100 = get_data('https://en.wikipedia.org/wiki/NASDAQ-100', 'nasdaq_100_cache.pkl', 4)
    nasdaq_100_tickers = nasdaq_100['Ticker'].tolist()

    set1 = set(sp500_tickers)
    set2 = set(nasdaq_100_tickers)

    # Merge sets and remove duplicates
    merged_set = set1.union(set2)
    return list(merged_set)


def process_all_tickers_and_symbols(DB_Company, DB_Ticker):
    # Read and print the stock tickers that make up S&P500
    sp500 = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')[0]
    print(sp500.head())
    sp500_tickers = sp500['Symbol'].tolist()

    nasdaq_100 = pd.read_html('https://en.wikipedia.org/wiki/NASDAQ-100')[4]
    nasdaq_100_tickers = nasdaq_100['Ticker'].tolist()

    for c in nasdaq_100:
        company_name = c['Company']
        q = Q(company_name=company_name)

        print(company_name)

    #for t in nasdaq_100_tickers:
    #    q = Q(Company=current_user.username) & Q(id=ticker_id)
    #    ticker = DB_Ticker.objects(q).first()

    return sp500_tickers

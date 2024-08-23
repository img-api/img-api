import os
import re

import requests
import requests_cache

import pandas as pd
import yfinance as yf

from datetime import timedelta

from api.print_helper import *
from api.company.models import DB_Company

from .models import DB_Ticker

# Perform complex queries to mongo
from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q


def get_data(url, cache_file, index):
    if os.path.exists(cache_file):
        return pd.read_pickle(cache_file)

    df = pd.read_html(url)[index]
    df.to_pickle(cache_file)  # Save to cache
    return df


def get_data_with_links(url, cache_file, index):
    if os.path.exists(cache_file):
        return pd.read_pickle(cache_file)

    df = pd.read_html(url, extract_links="body")[index]
    df.to_pickle(cache_file)  # Save to cache
    return df


def get_jsondata(url, cache_file):
    if os.path.exists(cache_file):
        return pd.read_pickle(cache_file)

    df = pd.read_json(url)
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


def clean_company_name(name):
    # Remove any text in parentheses and everything that follows

    # Define a pattern to match all unwanted phrases
    unwanted_phrases = r"Common Shares of Beneficial Interest|Common Stock|Common shares|Common Shares|Ordinary Shares"
    name = re.sub(unwanted_phrases, "", name)

    # Remove any text in parentheses and everything that follows
    cleaned_name = re.sub(r'\s*\(.*\)', '', name)

    # Remove the last comma if it exists and strip any trailing spaces
    cleaned_name = cleaned_name.rstrip(',').strip()
    return cleaned_name.strip()


def update_needed(my_company, db_company):
    for key in my_company:
        if db_company[key] != my_company[key]:
            return True

    return False


def create_or_update_company(my_company):

    query = Q(company_name=my_company['company_name'])
    if 'gics_sector' in my_company:
        query = Q(gics_sector=my_company['gics_sector']) & query

    if 'gics_sub_industry' in my_company:
        query = Q(gics_sector=my_company['gics_sub_industry']) & query

    db_company = DB_Company.objects(query).first()
    if not db_company:
        print_b("Created: " + my_company['company_name'])

        db_company = DB_Company(**my_company)
        db_company.save(validate=False)
        return db_company

    # Update with the extra info if there is any

    if update_needed(my_company, db_company):
        print_b("Updated: " + my_company['company_name'])
        db_company.update(**my_company, validate=False)

    return db_company


# NASDAQ API helpers


def nasdaq_api_get_exchange(exchange):
    """ Extracted from the example of how to fetch from the NASDAQ api directly
        https://github.com/shilewenuw/get_all_tickers/blob/master/get_all_tickers/get_tickers.py
    """

    api_call = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000&exchange=" + exchange

    print("#################################")
    print(" LOADING: " + api_call)

    # Headers are required to look like a mozilla, otherwise Nasdaq will not return anything and hang it there.
    headers = {
        'authority': 'api.nasdaq.com',
        'accept': 'application/json, text/plain, */*',
        'user-agent':
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36',
        'origin': 'https://www.nasdaq.com',
        'sec-fetch-site': 'same-site',
        'sec-fetch-mode': 'cors',
        'sec-fetch-dest': 'empty',
        'referer': 'https://www.nasdaq.com/',
        'accept-language': 'en-US,en;q=0.9',
    }

    # Initialize the cache with an expiration time
    requests_cache.install_cache(exchange + '_cache', expire_after=86400)
    response = requests.get(api_call, timeout=10, headers=headers)

    if response.status_code != 200:
        print(" Failed calling API " + str(response.status_code) + " " + api_call)
        return

    data = response.json()

    # Extract headers and rows from the data
    headers = data['data']['table']['headers']
    rows = data['data']['table']['rows']

    for row in rows:
        my_company = {
            "company_name": clean_company_name(row['name']),
            "market_cap": row["marketCap"],
            "nasdaq_url": "https://www.nasdaq.com" + row['url'],
        }

        db_company = create_or_update_company(my_company)


def process_all_nasdaq():
    """ We can also explore the NASDAQ specific library: https://docs.data.nasdaq.com/docs/python-tables """

    try:
        nasdaq_api_get_exchange("nasdaq")
    except Exception as e:
        print_exception(e)


def process_all_nyse():
    """ Public api from nasdaq that provides all the results contains 2792 records
        URL extracted is relative to www.nasdaq.com, example:
            https://www.nasdaq.com/market-activity/stocks/kr
    """
    try:
        nasdaq_api_get_exchange("nyse")
    except Exception as e:
        print_exception(e)


def process_all_AMEX():
    """ Public api from nasdaq that provides all the results contains 298 records
    """
    try:
        nasdaq_api_get_exchange("amex")
    except Exception as e:
        print(e)


def process_all_tickers_and_symbols():
    process_all_nasdaq()
    process_all_nyse()

    # Read and print the stock tickers that make up S&P500
    sp500 = get_data_with_links('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies',
                                "sp_500_companies_with_url.pkl", 0)

    print(sp500.head())
    sp500_tickers = sp500['Symbol'].tolist()
    sp500_tickers = [rec[0] for rec in sp500_tickers]

    for index, row in sp500.iterrows():
        cik = row['CIK'][0]
        cik = int(cik) if cik.isdigit() else 0

        my_company = {
            "company_name": clean_company_name(row['Security'][0]),
            "gics_sector": row['GICS Sector'][0],
            "gics_sub_industry": row['GICS Sub-Industry'][0],
            "founded": row['Founded'][0],
            "headquarters": row['Headquarters Location'][0],
            "wikipedia": "https://en.wikipedia.org/wiki" + row['Security'][1],
            "CIK": cik,  # CIK = Central Index Key
        }

        db_company = create_or_update_company(my_company)

    # Symbol   Security GICS Sector  GICS Sub-Industry         Headquarters Location   Date added  CIK      Founded
    # MMM      3M       Industrials  Industrial ....           Saint Paul   Minnesota  1957-03-04  66740    1902

    nasdaq_100 = get_data_with_links('https://en.wikipedia.org/wiki/NASDAQ-100', 'nasdaq_100_cache_with_url.pkl', 4)

    nasdaq_100_tickers = nasdaq_100['Ticker'].tolist()
    nasdaq_100_tickers = [rec[0] for rec in nasdaq_100_tickers]

    print(nasdaq_100.columns.tolist())
    # Iterate over each row and access columns by title
    for index, row in nasdaq_100.iterrows():
        # Access specific columns by their titles

        # Example:
        # 'Company', 'Ticker', 'GICS Sector', 'GICS Sub-Industry'
        # Adobe Inc.	ADBE	Information Technology	Application Software

        my_company = {
            "company_name": clean_company_name(row['Company'][0]),
            "gics_sector": row['GICS Sector'][0],
            "gics_sub_industry": row['GICS Sub-Industry'][0],
            "wikipedia": "https://en.wikipedia.org/wiki" + row['Company'][1]
        }

        db_company = create_or_update_company(my_company)

        # Save and reload so we get an ID. This operation is very slow
        ticker = row['Ticker'][0]

        print(f"Row {index}: Company = {db_company.company_name}, Ticker = {ticker}")

    return sp500_tickers

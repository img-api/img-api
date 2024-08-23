import os
import re
import requests_cache
import yfinance as yf
import pandas as pd

from datetime import timedelta

from api.company.models import DB_Company

from .models import DB_Ticker


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


def clean_company_name(name):
    # Remove any text in parentheses and everything that follows
    cleaned_name = re.sub(r'\s*\(.*\)', '', name)
    return cleaned_name.strip()


def create_or_update_company(my_company):
    db_company = DB_Company.objects(company_name=my_company['company_name'],
                                    gics_sector=my_company['gics_sector'],
                                    gics_sub_industry=my_company['gics_sub_industry']).first()
    if not db_company:
        # Example:
        # 'Company', 'Ticker', 'GICS Sector', 'GICS Sub-Industry'
        # Adobe Inc.	ADBE	Information Technology	Application Software

        db_company = DB_Company(**my_company)
        db_company.save(validate=False)
        return db_company

    # Update with the extra info if there is any
    db_company.update(**my_company, validate=False)

    return db_company


def process_all_tickers_and_symbols():
    # Read and print the stock tickers that make up S&P500
    sp500 = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', extract_links="body")[0]
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
            "CIK": cik, # CIK = Central Index Key
        }

        db_company = create_or_update_company(my_company)

    # Symbol   Security GICS Sector  GICS Sub-Industry         Headquarters Location   Date added  CIK      Founded
    # MMM      3M       Industrials  Industrial ....           Saint Paul   Minnesota  1957-03-04  66740    1902

    nasdaq_100 = pd.read_html('https://en.wikipedia.org/wiki/NASDAQ-100', extract_links="body")[4]
    nasdaq_100_tickers = nasdaq_100['Ticker'].tolist()
    nasdaq_100_tickers = [rec[0] for rec in nasdaq_100_tickers]

    print(nasdaq_100.columns.tolist())
    # Iterate over each row and access columns by title
    for index, row in nasdaq_100.iterrows():
        # Access specific columns by their titles

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

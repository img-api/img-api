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

from .tickers_helpers import extract_exchange_ticker_from_url


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


def getPrices(ticker):
        
    '''searches for stock in database.
    if stock is not present, adds stock to database'''
    
    ticker = yf.Ticker(f"{ticker}")
    prices = ticker.history()
    income_statement = ticker.income_stmt
    balance_sheet = ticker.balance_sheet
    cash_flow = ticker.cash_flow

    return prices, income_statement, balance_sheet, cash_flow


def getRatios(ticker):
        
    '''given a stock ticker, grab its balance sheet, 
    income statement & cash flow statement and saves it into an excel file'''
    
    headers= {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:87.0) Gecko/20100101 Firefox/87.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0'
    }
    urls = {}
    
    
    urls['ratio annually'] = f"https://stockanalysis.com/stocks/{ticker}/financials/ratios/"
    urls['ratio quarterly'] = f"https://stockanalysis.com/stocks/{ticker}/financials/ratios/?period=quarterly"
    
    xlwriter = pd.ExcelWriter(f'financial_statements_{ticker}.xlsx', engine='xlsxwriter')
    
    for key in urls.keys():
        response = requests.get(urls[key], headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')
        df = pd.read_html(str(soup), attrs={'data-test': 'fintable'})[0]
        df.to_excel(xlwriter, sheet_name=key, index=False)
    
    xlwriter.save()

def getNewsHeader(self, ticker):
        
    '''getting news from finviz'''
    
    #work in progress
    
    url = "https://finviz.com/quote.ashx?t={ticker}&p=d"
    news_tables = {}
    
    req = Request(url=url, headers={"user-agent": "my-app"})
    response = urlopen(req)
    
    html = BeautifulSoup(response, "html") 
    news_table = html.find(id="news-table")
    rows = news_table.findAll("tr")
    links = []
    for idx, row in enumerate(rows):
        #get all links
        title = row.a.text
        date_data = row.td.text.split("")
        if len(date_data) == 1:
            time = date_data[0]
        else:
            date = date_data[0]
            time = date_data[1]
    
    return ticker, date, time, title

def getData(tickers = "default"):
        
    #work in progress
    '''given a list of tickers, get data from the internet'''
    if tickers == "default":
        tickers = self.get_all_tickers_and_symbols()
        self.tickers = tickers
    data = {}
    for ticker in tickers:
        price, is_, bs, cf = self.getPrices(ticker)
        ratios = self.getRatios(ticker)
        news = self.getNews(ticker)
        data[f"{ticker}"] = [price, is_, bs, cf, ratios, news]
    return data
    


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
        if key not in db_company:
            return True

        if db_company[key] != my_company[key]:
            return True

    return False


def create_or_update_company(my_company, exchange=None, ticker=None):
    db_company = None

    # We search first for the combination of ticker exchange in the format EXCHANGE:TICKER
    if exchange and ticker:
        if ticker == "INTC":
            print(" TEST ")

        query = Q(exchange_tickers=exchange + ":" + ticker)
        db_company = DB_Company.objects(query).first()

    if not db_company:
        query = Q(company_name=my_company['company_name'])
        db_company = DB_Company.objects(query).first()

    if not db_company:
        print_b("Created: " + str(exchange) + ":" + str(ticker) + " " + my_company['company_name'])

        # For us it is important to track tickers and exchanges in which companies trade
        if exchange:
            my_company['exchanges'] = [exchange]
            if ticker:
                my_company['exchange_tickers'] = [exchange + ":" + ticker]

        db_company = DB_Company(**my_company)
        db_company.save(validate=False)
        return db_company

    # Update with the extra info if there is any

    # We append an exchange for a company if it is not there.
    db_company.append_exchange(exchange, ticker)

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
            "nasdaq_url": "https://www.nasdaq.com" + row['url'],
            "source": "NASDAQ API",
            # "market_cap": row["marketCap"], Market cap should go to the ticker
        }
        db_company = create_or_update_company(my_company, exchange.upper(), row['symbol'])


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


def process_all_amex():
    """ Public api from nasdaq that provides all the results contains 298 records
    """
    try:
        nasdaq_api_get_exchange("amex")
    except Exception as e:
        print(e)


def process_all_tickers_and_symbols():

    # Read and print the stock tickers that make up S&P500
    sp500 = get_data_with_links('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies',
                                "sp_500_companies_with_url.pkl", 0)

    print(sp500.head())
    sp500_tickers = sp500['Symbol'].tolist()
    sp500_tickers = [rec[0] for rec in sp500_tickers]

    for index, row in sp500.iterrows():
        cik = row['CIK'][0]
        cik = int(cik) if cik.isdigit() else 0

        # URL https://www.nyse.com/quote/XNYS:MMM
        exchange_url = row['Symbol'][1]

        exchange, ticker = extract_exchange_ticker_from_url(exchange_url)

        my_company = {
            "company_name": clean_company_name(row['Security'][0]),
            "gics_sector": row['GICS Sector'][0],
            "gics_sub_industry": row['GICS Sub-Industry'][0],
            "founded": row['Founded'][0],
            "headquarters": row['Headquarters Location'][0],
            "wikipedia": "https://en.wikipedia.org/wiki" + row['Security'][1],
            "exchange_url": exchange_url,
            "CIK": cik,  # CIK = Central Index Key
            "source": "WIKIPEDIA",
        }

        db_company = create_or_update_company(my_company, exchange, ticker)

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
            "wikipedia": "https://en.wikipedia.org/wiki" + row['Company'][1],
            "source": "WIKIPEDIA",
        }

        ticker = row['Ticker'][0].upper()
        db_company = create_or_update_company(my_company, "NASDAQ", ticker)

        print(f"Row {index}: Company = {db_company.company_name}, Ticker = {ticker}")


    process_all_nasdaq()
    process_all_nyse()
    process_all_amex()

    return sp500_tickers

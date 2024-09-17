import os
import re


import requests
import requests_cache

import urllib
from urllib.request import urlopen, Request
import pandas as pd
import yfinance as yf

import time
import selenium
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options

import datetime
from datetime import timedelta

from api.print_helper import *
from api.company.models import DB_Company

from .models import DB_Ticker

# Perform complex queries to mongo
from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q

from .tickers_helpers import extract_exchange_ticker_from_url
from news.models import DB_news

firefox_user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:103.0) Gecko/20100101 Firefox/103.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:102.0) Gecko/20100101 Firefox/102.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:101.0) Gecko/20100101 Firefox/101.0",
        "Mozilla/5/.0 (Windows NT 10.0; Win64; x64; rv:100.0) Gecko/20100101 Firefox/100.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:103.0) Gecko/20100101 Firefox/103.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0",
        "Mozilla/5.0 (Linux x86_64; rv:103.0) Gecko/20100101 Firefox/103.0",
        "Mozilla/5.0 (Linux x86_64; rv:102.0) Gecko/20100101 Firefox/102.0"
    ]

proxy_list = [
    "180.183.157.159",
    "46.4.96.137",
    "47.91.88.100",
    "45.77.56.114",
    "82.196.11.105"
]

#News article pipeline
def get_yahoo_publishers():

    """Gets list of publishers connected to Yahoo Finance. Returns as a set object."""

    yahoo_publishers = set()
    tickers = ["AMGN", "KO", "MSFT", "NVDA", "WM"]
    for ticker in tickers:
        ticker = yf.Ticker(ticker)
        for item in ticker.news:
            yahoo_publishers.add(item["publisher"])
    return yahoo_publishers


            
#completed
def save_article(self, date, link, title, news_type, publisher, article, uuid, related_tickers = None):
    
    """Creates a MongoDB article object. 
    Saves article into the relevant database"""
    
    news = DB_News(
        creation_date = date,
        last_visited_date = datetime.datetime.now(),
        link = link,
        title = title,
        news_type = news_type,
        publisher = publisher,
        news_article = article,
        external_uuid = uuid,
        related_exchange_tickers = related_tickers
    )
    news.save()
    
    
def date_from_unix(string):

    """Takes unix format and converts it into datetime object"""

    return datetime.datetime.fromtimestamp(float(string))



#completed
def clean_article(article):

    """Takes in article string as input, removes all instances of \n from it."""

    article = re.sub("\n", " ", article)
    return article

#completed
def extract_domain_name(url):
    
    """Extracts domain name from a URL. Returns a string."""        
    
    parsed_url = urlparse(url)
    base_url = parsed_url.netloc
    base_url = re.sub("www.", "", base_url)
    base_url = re.sub(".com", "", base_url)
    return base_url

    
def download_yahoo_news(ticker):
    ticker = yf.Ticker(f"{ticker}")
    for item in ticker.news:
        if item["publisher"] not in ["Barrons", "MT Newswires", "Investor's Business Daily", "Yahoo Finance Video"]:
            success, article = download_article(item["link"])
            
            print(item["publisher"], article)
            if success == 0:
                news_type = "denied"
            elif success == 1:
                news_type = "html"
            else:
                news_type = "text"
            save_article(
                        date = date_from_unix(item["providerPublishTime"]),
                        link = item["link"],
                        title = item["title"],
                        news_type = news_type,
                        publisher = item["publisher"],
                        article = article,
                        uuid = "Y_" + item["uuid"],
                    related_tickers = item["relatedTickers"])
        else:
            if item["publisher"] == "Investor's Business Daily":
                success, html = download_ibd(item["link"])
                print("Investor's Business Daily", html)
                if success == 1:
                    news_type = "html"
                else:
                    news_type = "denied"
                save_article(
                        date = date_from_unix(item["providerPublishTime"]),
                        link = item["link"],
                        title = item["title"],
                        news_type = news_type,
                        publisher = item["publisher"],
                        article = article,
                        uuid = "Y_" + item["uuid"],
                    related_tickers = item["relatedTickers"])
        

def download_article(url):
    user_agent = random.choice(firefox_user_agents)
    options = Options()
    options.set_preference("general.useragent.override", user_agent)
    driver = webdriver.Firefox(options=options)
    try:
        driver.get(url)
    
    except:
        #save into denied
        return [0, ""]
    
    try:
        # Wait until the button is visible
        readmore_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CLASS_NAME, "readmore-button"))
        )

        # Optionally, scroll to the button if necessary
        actions = ActionChains(driver)
        actions.move_to_element(readmore_button).perform()

        # Click the button
        readmore_button.click()
    
        print("Clicked on the 'Read More' button successfully.")

    except Exception as e:
        print(f"Error: {e}")
    
    time.sleep(random.randint(2,10)) 
    
    try:
        html = driver.page_source
    except Exception as e:
        print(f"Error: {e}")
        driver.quit()
        return [0, ""]
    try:
        article = driver.find_element(By.TAG_NAME, "article")
        article = clean_article(article.text)
        driver.quit()
        return [2, article]
    except Exception as e:
        print(f"Error: {e}, {url}")
        driver.quit()
        return [1, html]



                
def download_ibd(url):
    user_agent = random.choice(firefox_user_agents)
    options = Options()
    options.set_preference("general.useragent.override", user_agent)
    driver = webdriver.Firefox(options=options)

    driver.get(url)
    time.sleep(random.randint(4,7))
    try:
        link = driver.find_element(By.LINK_TEXT, "Continue Reading")
        link.click()
    except:
        pass
    
    time.sleep(5)
    try:
        html = driver.page_source
    except:
        return [0, ""]

    try:
        article = driver.find_element(By.TAG_NAME, "article")
    except:
        return [1, html]
    article = clean_article(article.text)
    driver.quit()
    return [2, article]
        
def reprocess():
    
    return



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


def get_prices(ticker):
        
    """searches for stock in database.
    if stock is not present, adds stock to database"""
    
    ticker = yf.Ticker(f"{ticker}")
    prices = ticker.history()
    income_statement = ticker.income_stmt
    balance_sheet = ticker.balance_sheet
    cash_flow = ticker.cash_flow

    return prices, income_statement, balance_sheet, cash_flow



def get_ratios(ticker):
        
    """Given a stock ticker, grab its balance sheet, 
    income statement & cash flow statement and saves it into an excel file"""
    
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

        # We create tickers, consult yahoo for the ticker and process everything.
        db_ticker = create_or_update_ticker(db_company, exchange, ticker)

        return db_company

    # Update with the extra info if there is any

    # We append an exchange for a company if it is not there.
    db_company.append_exchange(exchange, ticker)

    if update_needed(my_company, db_company):
        print_b("Updated: " + my_company['company_name'])
        db_company.update(**my_company, validate=False)

    # We create tickers, consult yahoo for the ticker and process everything.
    db_ticker = create_or_update_ticker(db_company, exchange, ticker)

    return db_company


def create_or_update_ticker(db_company, exchange=None, ticker=None):
    """ A company can have multiple tickers in different exchanges

        A ticker has stock prices and multiple information related to the exchange

    """
    db_ticker = None

    # We search first for the combination of ticker exchange in the format EXCHANGE:TICKER
    if exchange and ticker:
        query = Q(exchange=exchange) & Q(ticker=ticker)
        db_ticker = DB_Ticker.objects(query).first()

    if db_ticker:
        return db_ticker

    print_b(" CREATE NEW TICKER " + exchange + ":" + ticker)

    my_ticker = {
        "company_id": str(db_company.id),
        "exchange": exchange,
        "ticker": ticker,
    }

    db_ticker = DB_Ticker(**my_ticker)
    db_ticker.save(validate=False)
    return db_ticker


# NASDAQ API helpers


def nasdaq_api_get_exchange(exchange):
    """ Extracted from the example of how to fetch from the NASDAQ api directly
        https://github.com/shilewenuw/get_all_tickers/blob/master/get_all_tickers/get_tickers.py
    """

    print_h1(" FREE API NASDAQ " + exchange)

    api_call = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000&exchange=" + exchange

    exchange = exchange.upper()

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

        ticker = row['symbol']

        db_company = create_or_update_company(my_company, exchange, ticker)


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

def process_all_frankfurt_stock_exchange():
    print(" FRANKFURT STOCK DE ")
    # ticker_symbol = 'BMW.DE'  # Example: 'BMW.DE' for BMW on the Frankfurt Stock Exchange

    # Download from here?
    # https://www.deutsche-boerse-cash-market.com/dbcm-en/instruments-statistics/statistics/listes-companies


def process_all_tickers_and_symbols():
    """
        Brute force finding of different Companies and tickers looking at different Sources
        This will be splitted later into a process to run in a schedule.
    """

    print_h1(" DISCOVERY START ")

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

    print_h1(" DISCOVERY FINISHED ")
    return sp500_tickers


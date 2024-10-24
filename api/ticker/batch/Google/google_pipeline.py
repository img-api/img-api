import datetime
import requests
import re

from pygooglenews import GoogleNews
from google_news import *
from api.print_helper import *
from api.query_helper import *
from api.news.models import DB_DynamicNewsRawData, DB_News
from api.ticker.models import DB_Ticker, DB_TickerSimple
from api.ticker.tickers_helpers import (standardize_ticker_format,
                                        standardize_ticker_format_to_yfinance)

def parse_google_dates(date_str):
    
    """Parses dates from Google News"""

    parsed_date = datetime.datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z")
    # Format the date into the desired format
    formatted_date = parsed_date.strftime("%Y-%m-%d %H:%M:%S")
    return formatted_date

def format_google_dates(date):
    date = re.sub("-", "", date)
    date = re.sub(" ", "", date)
    date = re.sub(":", "", date)
    return date

def get_google_news(db_ticker):
    
    google_news_publishers = ["24/7 Wall St.","Barchart", "Benzinga", "Fast Company", "Forbes", "ForexLive", "Fortune", "FXStreet",
                                "Insider Monkey", "Investing.com", "Investopedia", "Investor's Business Daily", "MarketBeat",
                                "Markets.com", "Marketscreener.com", "MoneyCheck", "Nasdaq", "Proactive Investors USA", "Reuters",
                                "StockTitan", "TipRanks", "TradingView", "Watcher Guru"]
    ticker = db_ticker.ticker    
    news = []
    gn = GoogleNews()
    search = gn.search(f"{ticker}")
    for item in search["entries"]:
        if item["source"]["title"] in google_news_publishers:
            news.append(item)
    return news

def google_pipeline_process(db_ticker):
    news = get_google_news(db_ticker)
    for item in news:
        update = False
        db_news = DB_News.objects(external_uuid=item["id"]).first()
        if db_news:
            # We don't update news that we already have in the system
            print_b(" ALREADY INDEXED " + item['link'])
            update = True
            #continue
    
        raw_data_id = 0
        try:
            # It should go to disk or something, this is madness to save it on the DB
    
            news_data = DB_DynamicNewsRawData(**item)
            news_data.save()
            raw_data_id = str(news_data['id'])
        except Exception as e:
            print_exception(e, "SAVE RAW DATA")
    
        #standardize between the different news sources
        #alpha vantage doesn't have related tickers*
        new_schema = {
                    "date": parse_google_dates(item["published"]),
                    "title": item["title"],
                    "link": item["link"],
                    "external_uuid": item["id"],
                    "publisher": item["source"]
                }
        .
        myupdate = prepare_update_with_schema(item, new_schema)
    
        extra = {
            'source': 'GOOGLE',
            'status': 'WAITING_INDEX',
            'raw_data_id': raw_data_id
        }
    
        myupdate = {**myupdate, **extra}
    
        if not update:
            db_news = DB_News(**myupdate).save(validate=False)
        
        google = Google()
        article = google.process_google_news(db_news)
        if article != "":
            db_news.article = articles
            db_news.save(validate=False)
            db_news.set_state("INDEXED")
        else:
            db_news.set_state("ERROR: ARTICLES NOT FOUND")

    return db_ticker


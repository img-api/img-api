import datetime
import re

import requests
from api.news.models import DB_DynamicNewsRawData, DB_News
from api.print_helper import *
from api.query_helper import *
from api.ticker.batch.alpha_vantage.alpha_vantage_news import *
from api.ticker.models import DB_Ticker, DB_TickerSimple
from api.ticker.tickers_helpers import (standardize_ticker_format,
                                        standardize_ticker_format_to_yfinance)


def parse_av_dates(date_string):
    parsed_date = datetime.datetime.strptime(date_string, '%Y%m%dT%H%M%S')
    return parsed_date

def format_av_dates(date):
    date = re.sub("-", "", date)
    date = re.sub(" ", "", date)
    date = re.sub(":", "", date)
    return date

def generate_external_uuid(item, ticker):
    date = parse_av_date(item["time_published"])
    date = format_av_dates(date)
    return f"av_{ticker}_{date}"


def get_av_news(db_ticker):

    exchange = db_ticker.exchange
    ticker = db_ticker.ticker
    if exchange in ["NYSE", "NASDAQ", "NYQ", "NYE"]:
        news = get_us_news(ticker)
        return news
    else:
        print("Functionality not available yet")
        return []

def get_us_news(ticker):
    news = []
    url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={ticker}&apikey=JIHXVRY5SPIH16C9"
    r = requests.get(url)
    data = r.json()
    for news_item in data["feed"]:
        if news_item["source"] in ["CNBC", "Money Morning", "Motley Fool", "South China Morning Post", "Zacks Commentary"]:
            relevance_score = get_relevance_score(ticker)
            if relevance_score > 0.4:
                news.append(news_item)
    return news

def get_relevance_score(news_item, ticker):
    for item in news["ticker_sentiment"]:
        if item["ticker"] == ticker:
            return float(item["relevance_score"])
    return 0



def av_pipeline_process(db_ticker):

    ticker = db_ticker.ticker
    news = get_av_news(ticker)
    if news == []:
        print("No AV news found")
        db_ticker.set_state("PROCESSED")
        return db_ticker


    for item in news:
        update = False
        external_uuid = generate_external_uuid(item, ticker)
        db_news = DB_News.objects(external_uuid=external_uuid).first()
        if db_news:
            # We don't update news that we already have in the system
            print_b(" ALREADY INDEXED ")
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
        date = parse_av_date(item["time_published"])
        new_schema = {
                    "date": date,
                    "title": item["title"],
                    "link": item["url"],
                    "external_uuid": external_uuid,
                    "publisher": item["source"]
                }


        myupdate = prepare_update_with_schema(item, new_schema)

        related_tickers = []
        for ticker_item in news["ticker_sentiment"]:

            if ticker_item["ticker"] == db_ticker.ticker:
                related_tickers.append(db_ticker.full_symbol())
            else:
                full_symbol = get_full_symbol(ticker)
                related_tickers.append(full_symbol)

        myupdate['related_exchange_tickers'] = related_tickers

        extra = {
            'source': 'ALPHAVANTAGE',
            'status': 'WAITING_INDEX',
            'raw_data_id': raw_data_id
        }

        myupdate = {**myupdate, **extra}

        if not update:
            db_news = DB_News(**myupdate).save(validate=False)

        av = AlphaVantage()
        article = av.process_av_news(db_news)
        if article != "":
            db_news.article = article
            db_news.save(validate=False)
            db_news.set_state("INDEXED")
        else:
            db_news.set_state("ERROR: ARTICLE NOT FOUND")

    db_ticker.set_state("AV PROCESSED")
    return db_ticker

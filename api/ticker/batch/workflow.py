import os
import re
from datetime import timedelta

import pandas as pd
import requests
import requests_cache
from api.company.models import DB_Company
from api.news.models import DB_News
from api.print_helper import *
from api.query_helper import *
from api.ticker.models import DB_Ticker
# Perform complex queries to mongo
from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q

import yfinance as yf

from .tickers_pipeline import ticker_pipeline_process
from .yfinance.yfinance_news import yfetch_process_news
from .yfinance.ytickers_pipeline import yticker_pipeline_process

# RAW basic implementation before going for a future implmentation using
# Something like temporal.io

# https://learn.temporal.io/getting_started/python/first_program_in_python/


def ticker_process_news_sites(BATCH_SIZE=5):
    """ Fetches all the news to be indexed and calls the API to fetch them
        We don't have yet a self-registering plugin api so we will just call manually depending on the source.
    """
    query = Q(force_reindex=True)
    news = DB_News.objects(query)[:BATCH_SIZE]
    if news.count() == 0:
        query = Q(status='WAITING_INDEX')
        news = DB_News.objects(query)[:BATCH_SIZE]

    for item in news:
        try:
            if item.force_reindex:
                item.update(**{ 'force_reindex': False })

            item.set_state("INDEX_START")

            if item.source == "YFINANCE":
                yfetch_process_news(item)
                continue

            elif item.source == "AlphaVantage":
                alpha_vantage_332process_news(item)

            elif item.source == "Google":
                google_process_news(item)

        except Exception as e:
            item.set_state("ERROR: FETCH CRASHED, SEE LOGS!")
            print_exception(e, "CRASHED FETCHING NEWS")

    return news

def kill_chrome():
    import os
    import signal

    import psutil

    cmdline_pattern = ['/home/dev/chrome/linux-116.0.5793.0/chrome-linux64/chrome']
    for process in psutil.process_iter(['pid', 'cmdline']):
        cmdline = process.info['cmdline']
        if cmdline == cmdline_pattern:
            print(f"Found process: PID = {process.info['pid']}, Command Line: {' '.join(cmdline)}")
            os.kill(process.info['pid'], signal.SIGKILL)

def ticker_process_batch(end=None, dry_run=False, BATCH_SIZE=10):
    """
    Gets a list of tickers and calls the different APIs to capture and process the data.

    Limit to BATCH_SIZE so we don't ask for too many at once to all APIs
    """

    # Get tickers processed more than X days ago.
    # Less than or Equal to Last processed

    if not end:
        end = datetime.fromtimestamp(get_timestamp_verbose("1 days"))

    query = Q(force_reindex=True)
    tickers = DB_Ticker.objects(query)[:BATCH_SIZE]
    if tickers.count() == 0:
        query = Q(last_processed_date__lte=end) | Q(last_processed_date=None)
        tickers = DB_Ticker.objects(query)[:BATCH_SIZE]

    for db_ticker in tickers:
        if db_ticker.force_reindex:
            db_ticker.update(**{ 'force_reindex': False })

        db_ticker.set_state("PIPELINE_START")

        # We process every ticker with a different pipeline.
        # Parsers should self-register to provide support. TBD
        try:
            yticker_pipeline_process(db_ticker, dry_run=dry_run)
        except Exception as e:
            print_exception(e, "CRASHED PROCESSING BATCH")

    #kill_chrome()
    return tickers


def ticker_process_invalidate(ticker):

    query = Q(ticker=ticker)
    tickers = DB_Ticker.objects(query)
    for db_ticker in tickers:
        db_ticker.set_state("PIPELINE_START")

        try:
            yticker_pipeline_process(db_ticker)
        except Exception as e:
            print_exception(e, "CRASHED PROCESSING BATCH")

    return tickers

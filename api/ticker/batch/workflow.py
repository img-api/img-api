import os
import re
from collections import Counter
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
from .yfinance.ytickers_pipeline import (yticker_check_tickers,
                                         yticker_pipeline_process)

####################################
# PROCESS TO MICROSERVICE PLAN
####################################

# GET TICKERS THAT HAVE NOT BEING PROCESSED
# https://domain/api/ticker/index/batch/get_tickers?lte=1%20hour&limit=1

# FIND NEWS THAT HAVE NOT BEING PROCESSED:
# https://domain/api/news/query?status=WAITING_INDEX&limit=1

# UPDATE NEWS [WIP]
#  https://domain/api/news/update [POST]

# RAW basic implementation before going for a future implmentation using
# Something like temporal.io

# https://learn.temporal.io/getting_started/python/first_program_in_python/


def ticker_reprocess_news_article(item):
    """
    http://dev.tothemoon.life/api/news/get/67631451ad0c775b1f8b33c1?no_cache=1&extra=reprocess
    """

    from api.ticker.tickers_helpers import standardize_ticker_format

    try:
        if item.source != "YFINANCE":
            return

        item.force_reindex = True

        yticker_check_tickers(item['raw_tickers'], item)
        yfetch_process_news(item)

    except Exception as e:
        print_exception(e, "crashed")

    return item


def ticker_process_news_sites(BATCH_SIZE=5):
    """ Fetches all the news to be indexed and calls the API to fetch them
        We don't have yet a self-registering plugin api so we will just call manually depending on the source.
    """
    from api.news.routes import (api_create_article_ai_summary,
                                 api_test_news_tickers_call)
    print_big(" NEWS BATCH ")

    update = False

    ai_timeout = datetime.fromtimestamp(get_timestamp_verbose("30 minutes"))

    item_news = DB_News.objects(ai_summary=None, last_visited_date__lte=ai_timeout,
                                articles__not__size=0).order_by('-creation_date').limit(10)

    for article in item_news:
        try:
            api_create_article_ai_summary(article)
            article.set_state("RETRY_AI_INDEX")
        except Exception as e:
            print_exception(e, "CRASHED")
            pass

    query = Q(force_reindex=True)
    news = DB_News.objects(query)[:BATCH_SIZE]
    if news.count() == 0:
        query = Q(status='WAITING_INDEX')
        news = DB_News.objects(query)[:BATCH_SIZE]

    #if news.count() == 0:
    #    print_r(" PROCESSING INDEXED NEWS THAT FAILED FOR SOME REASON 1 ")
    #    query = Q(status='INDEXED') & Q(ai_summary=None)
    #    news = DB_News.objects(query)[:BATCH_SIZE]

    #if news.count() == 0:
    #    print_r(" PROCESSING INDEXED NEWS THAT FAILED FOR SOME REASON 2 ")
    #    query = Q(ai_summary=None)
    #    news = DB_News.objects(query)[:BATCH_SIZE * 10]

    for item in news:
        try:
            if item.source_title:
                print(str(item.source) + " PROCESSING ITEM " + str(item.source_title))
            elif item.title:
                item.update(**{'source_title': item.title})
                print(str(item.source) + " PROCESSING ITEM TITLE " + str(item.title))
            else:
                print(str(item.source) + " PROCESSING ITEM - MISSING TITLE " + str(item.id))

            if item.force_reindex:
                item.update(**{'force_reindex': False})

            item.set_state("INDEX_START")

            #if item.source == "YFINANCE":
            yfetch_process_news(item)
            api_test_news_tickers_call(item)

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

    from api.company.routes import api_build_company_state_query

    # Ignore the end, we always want to process data now
    #if not end:
    #    end = datetime.fromtimestamp(get_timestamp_verbose("1 days"))

    query = Q(force_reindex=True)
    # Newest first
    tickers = DB_Ticker.objects(query).order_by('+last_processed_date')[:BATCH_SIZE]

    # Order by oldest, always returns a result
    if tickers.count() == 0:
        tickers = DB_Ticker.objects().order_by('+last_processed_date')[:BATCH_SIZE]

    for db_ticker in tickers:
        if db_ticker.force_reindex:
            db_ticker.update(**{'force_reindex': False})

        db_ticker.set_state("PIPELINE_START")

        try:
            api_build_company_state_query(db_ticker.get_company())
        except Exception as e:
            print_exception(e, "CRASHED PROCESSING BATCH")

        # We process every ticker with a different pipeline.
        # Parsers should self-register to provide support. TBD
        try:
            yticker_pipeline_process(db_ticker, dry_run=dry_run)
        except Exception as e:
            print_exception(e, "CRASHED PROCESSING BATCH")
            db_ticker.delete()

    #kill_chrome()
    return tickers


def ticker_process_invalidate_full_symbol(full_symbol):
    from api.ticker.tickers_helpers import split_full_symbol

    exchange, ticker = split_full_symbol(full_symbol)

    query = Q(ticker=ticker) & Q(exchange=exchange)
    tickers = DB_Ticker.objects(query)
    for db_ticker in tickers:
        db_ticker.set_state("PIPELINE_START")

        try:
            yticker_pipeline_process(db_ticker)
        except Exception as e:
            print_exception(e, "CRASHED PROCESSING BATCH")

    return tickers


def ticker_process_invalidate(ticker, max_age_minutes=5):

    query = Q(ticker=ticker)
    db_ticker = DB_Ticker.objects(query).first()
    #for db_ticker in tickers:

    #if db_ticker.age_minutes() < max_age_minutes:
    #    return

    try:
        db_ticker.set_state("PIPELINE_START")
        yticker_pipeline_process(db_ticker)
    except Exception as e:
        print_exception(e, "CRASHED PROCESSING BATCH")

    return [db_ticker]

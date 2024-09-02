import os
import re
import json

import requests
import requests_cache

import pandas as pd
import yfinance as yf

from datetime import timedelta

from api.print_helper import *
from api.query_helper import *

from api.company.models import DB_Company

from api.ticker.models import DB_Ticker, DB_TickerSimple
from api.news.models import DB_News, DB_DynamicNewsRawData

# Perform complex queries to mongo
from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q

from api.query_helper import copy_replace_schema
from api.ticker.connector_yfinance import fetch_tickers_info
from api.ticker.tickers_helpers import standardize_ticker_format_to_yfinance, standardize_ticker_format
from api.ticker.batch.yfinance.yfinance_news import yfetch_process_news


def ticker_update_financials(full_symbol, max_age_minutes=2):
    """ This is a very slow ticker fetch system, we use yfinance here
        But we could call any of the other APIs
    """

    fin = DB_TickerSimple.objects(exchange_ticker=full_symbol).first()

    if fin and fin.age_minutes() < max_age_minutes:
        return fin

    yticker = standardize_ticker_format_to_yfinance(full_symbol)
    yf_obj = fetch_tickers_info(yticker, no_cache=True)

    #if not yf_obj.info['currentPrice']:
    #    return fin

    new_schema = {
        'company_name': 'longName',
        'price': 'currentPrice',
        'ratio': 'currentRatio',
        'day_low': 'dayLow',
        'day_high': 'dayHigh',
        'current_open': 'open',
        'previous_close': 'previousClose',
        'volume': 'volume',
        'bid': 'bid',
        'bid_size': 'bidSize',
    }

    financial_data = prepare_update_with_schema(yf_obj.info, new_schema)
    financial_data['exchange_ticker'] = full_symbol

    if not fin:
        fin = DB_TickerSimple(**financial_data)
        fin.save(validate=False)
    else:
        fin.update(**financial_data, validate=False)

    return fin


def yticker_pipeline_process(db_ticker, dry_run=False):
    """
        Our fetching pipeline will call different status
    """
    from api.ticker.routes import get_full_symbol

    print_b("PROCESSING: " + db_ticker.full_symbol())

    yticker = standardize_ticker_format_to_yfinance(db_ticker.full_symbol())

    db_ticker.set_state("YFINANCE", dry_run)

    no_cache = request.args.get("no_cache", True)
    if no_cache == "0":
        no_cache = False

    yf_obj = fetch_tickers_info(yticker, no_cache=no_cache)

    if not yf_obj:
        db_ticker.set_state("FAILED YFINANCE", dry_run)
        return

    db_company = db_ticker.get_company()

    info = yf_obj.info

    new_schema = {
        'website': 'website',
        'long_name': 'longName',
        'long_business_summary': 'longBusinessSummary',
        'main_address': 'address1',
        'main_address_1': 'address2',
        'city': 'city',
        'state': 'state',
        'zipcode': 'zip',
        'country': 'country',
        'phone_number': 'phone',
        'gics_sector': 'sector',
        'gics_sub_industry': 'industry',
    }

    myupdate = prepare_update_with_schema(info, new_schema)

    if 'companyOfficers' in info:
        company_officers = info['companyOfficers']
        for officer in company_officers:
            print_b(f"TODO: Create person {officer['name']} => {officer['title']}")

    try:
        news = yf_obj.news
        for item in news:
            print_b(" PROCESS " + item['link'])

            db_news = DB_News.objects(external_uuid=item['uuid']).first()
            if db_news:
                # We don't update news that we already have in the system
                print_b(" ALREADY INDEXED " + item['link'])
                continue

            raw_data_id = 0
            try:
                # It should go to disk or something, this is madness to save it on the DB

                news_data = DB_DynamicNewsRawData(**item)
                news_data.save()
                raw_data_id = str(news_data['id'])
            except Exception as e:
                print_exception(e, "SAVE RAW DATA")

            new_schema = {
                'link': 'link',
                'external_uuid': 'uuid',
                'publisher': 'publisher',
                'related_exchange_tickers': 'relatedTickers',
            }

            myupdate = prepare_update_with_schema(item, new_schema)

            # We need to convert between both systems
            related_tickers = []

            for ticker in item['relatedTickers']:

                if ticker == db_ticker.ticker:
                    related_tickers.append(db_ticker.full_symbol())
                else:
                    full_symbol = get_full_symbol(ticker)
                    related_tickers.append(full_symbol)

            myupdate['related_exchange_tickers'] = related_tickers

            extra = {
                'source': 'YFINANCE',
                'status': 'WAITING_INDEX',
                'raw_data_id': raw_data_id,
            }

            myupdate = {**myupdate, **extra}

            db_news = DB_News(**myupdate).save(validate=False)
            yfetch_process_news(db_news)

    except Exception as e:
        print_exception(e, "CRASH ON YAHOO NEWS PROCESSING")

    if not dry_run:
        db_company.update(**myupdate, validate=False)
        db_ticker.set_state("PROCESSED", dry_run)

    return db_ticker
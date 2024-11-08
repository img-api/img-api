import json
import os
import re
from datetime import datetime, timedelta

import pandas as pd
import requests
import requests_cache
from api.company.models import DB_Company
from api.news.models import DB_DynamicNewsRawData, DB_News
from api.print_helper import *
from api.query_helper import *
from api.query_helper import copy_replace_schema
from api.ticker.batch.yfinance.yfinance_news import yfetch_process_news
from api.ticker.connector_yfinance import fetch_tickers_info
from api.ticker.models import DB_Ticker, DB_TickerSimple
from api.ticker.tickers_helpers import (standardize_ticker_format,
                                        standardize_ticker_format_to_yfinance)
# Perform complex queries to mongo
from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q

import yfinance as yf


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

    try:
        financial_data = prepare_update_with_schema(yf_obj.info, new_schema)
    except Exception as e:
        return fin

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
    from api.company.routes import api_create_ai_summary
    from api.news.routes import api_create_news_ai_summary
    from api.ticker.routes import get_full_symbol

    print_b("PROCESSING: " + db_ticker.full_symbol())

    yticker = standardize_ticker_format_to_yfinance(db_ticker.full_symbol())

    db_ticker.set_state("YFINANCE")

    no_cache = request.args.get("no_cache", True)
    if no_cache == "0":
        no_cache = False

    yf_obj = fetch_tickers_info(yticker, no_cache=no_cache)

    if not yf_obj:
        db_ticker.set_state("FAILED YFINANCE")
        return

    db_company = db_ticker.get_company()
    try:
        api_create_ai_summary(db_company)
    except Exception as e:
        pass

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

    company_update = prepare_update_with_schema(info, new_schema)

    if 'companyOfficers' in info:
        company_officers = info['companyOfficers']
        #for officer in company_officers:
        #    print_b(f"TODO: Create person {officer['name']} => {officer['title']}")

    if not dry_run:
        if not db_company:
            print_b("NO COMPANY WTF")
        else:
            db_company.update(**company_update, validate=False)

    try:
        news = yf_obj.news
        for item in news:
            print_b(" PROCESS " + item['link'])

            update = False
            db_news = DB_News.objects(external_uuid=item['uuid']).first()
            if db_news:
                # We don't update news that we already have in the system
                print_b(" ALREADY INDEXED ")
                update = True

                try:
                    api_create_news_ai_summary(db_news)
                except Exception as e:
                    print_exception(e, "CRASHED")
                    pass

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
                'title': 'title',
                'link': 'link',
                'external_uuid': 'uuid',
                'publisher': 'publisher',
                'related_exchange_tickers': 'relatedTickers',
            }

            myupdate = prepare_update_with_schema(item, new_schema)

            # Overwrite our creation time with the publisher time
            try:
                if 'providerPublishTime' in item:
                    value = datetime.fromtimestamp(int(item['providerPublishTime']))
                    print_b(" DATE " + str(value))
                    myupdate['creation_date'] = value
            except Exception as e:
                print_e(e, "CRASHED LOADING DATE")

            # We need to convert between both systems
            related_tickers = []

            if 'relatedTickers' in item:
                for ticker in item['relatedTickers']:

                    if ticker == db_ticker.ticker:
                        related_tickers.append(db_ticker.full_symbol())
                    else:
                        full_symbol = get_full_symbol(ticker)
                        related_tickers.append(full_symbol)

                myupdate['related_exchange_tickers'] = related_tickers
            else:
                print_r(" NO RELATED TICKERS ")

            try:
                if 'currentPrice' in info:
                    myupdate['stock_price'] = info['currentPrice']

            except Exception as e:
                print_exception(e, " PRICE DURING NEWS ")

            extra = {
                'source': 'YFINANCE',
                'status': 'WAITING_INDEX',
                'raw_data_id': raw_data_id,
            }

            myupdate = {**myupdate, **extra}

            if not update:
                db_news = DB_News(**myupdate).save(validate=False)

            yfetch_process_news(db_news)
            db_ticker.set_state("PROCESSED")

    except Exception as e:
        print_exception(e, "CRASH ON YAHOO NEWS PROCESSING")

    return db_ticker

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
from api.ticker.models import DB_Ticker, DB_TickerSimple, DB_TickerTimeSeries
from api.ticker.tickers_helpers import (extract_ticker_from_symbol,
                                        standardize_ticker_format,
                                        standardize_ticker_format_to_yfinance)
# Perform complex queries to mongo
from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q

import yfinance as yf


def fetch_historical_data(full_symbol, start_date=None, end_date=None, interval='1mo'):
    """
    Fetch historical data for the given ticker using yfinance.

    Args:
        full_symbol (str): The ticker symbol.
        start_date (str): Start date in 'YYYY-MM-DD' format. Defaults to one year ago.
        end_date (str): End date in 'YYYY-MM-DD' format. Defaults to today.
        interval (str): Data interval (e.g., '1d', '1wk', '1mo').

    Returns:
        pandas.DataFrame: Historical data.
    """
    # Default to one year of data if no dates are provided
    if not start_date:
        start_date = (datetime.today() - timedelta(days=365)).strftime('%Y-%m-%d')
    if not end_date:
        end_date = datetime.today().strftime('%Y-%m-%d')

    yticker = standardize_ticker_format_to_yfinance(full_symbol)

    try:
        # Fetch data
        historical_data = yf.download(yticker, start=start_date, end=end_date, interval=interval)
        if historical_data.empty:
            raise ValueError("No data fetched for ticker.")
    except Exception as e:
        print(f"Error fetching historical data: {e}")
        return None

    return historical_data


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
        ticker_save_financials(full_symbol, yf_obj)
    except Exception as e:
        #print_exception(e, "CRASH")
        return fin

    financial_data['exchange_ticker'] = full_symbol

    if not fin:
        fin = DB_TickerSimple(**financial_data)
        fin.save(validate=False)
    else:
        fin.update(**financial_data, validate=False)

    return fin


def ticker_save_financials(full_symbol, yf_obj, max_age_minutes=5):
    """ This is a very slow ticker fetch system, we use yfinance here
        But we could call any of the other APIs
    """
    try:
        fin = DB_TickerTimeSeries.objects(exchange_ticker=full_symbol).order_by("-creation_date").limit(1).first()

        if fin and fin.age_minutes() < max_age_minutes:
            return fin

        if not yf_obj or not yf_obj.info:
            return

        if 'currentPrice' not in yf_obj.info:
            return

        if not yf_obj.info['currentPrice']:
            return fin

        new_schema = {
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

        fin = DB_TickerTimeSeries(**financial_data)
        fin.save(validate=False)

        return fin

    except Exception as e:
        print_exception(e, "CRASHED SAVING FINANCIALS ")
        return None


def yticker_check_tickers(relatedTickers):
    from api.ticker.tickers_fetches import create_or_update_company

    try:
        result = []
        for local_ticker in relatedTickers:
            query = DB_Ticker.query_exchange_ticker(local_ticker)
            db_ticker = DB_Ticker.objects(query).first()
            if db_ticker:
                result.append(db_ticker.full_symbol())
                continue

            stock = extract_ticker_from_symbol(local_ticker)
            yf_obj = fetch_tickers_info(stock, no_cache=False)
            if not yf_obj:
                continue

            info = yf_obj.info
            if not info:
                print_r(" NO Info fould for ticker? ")
                return

            if 'symbol' not in info:
                print_r(" No ticker? ")
                return

            ticker = info['symbol']
            exchange = info['exchange']
            my_company = info['longName']

            new_schema = {
                'website': 'website',
                'company_name': 'longName',
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

            my_company = prepare_update_with_schema(info, new_schema)
            db_company = create_or_update_company(my_company, exchange, ticker)

            result.append(db_company.exchange_tickers[-1])
    except Exception as e:
        print_exception(e, "CRASHED FINDING NEW TICKERS")
        return None

    return result


def fix_news_ticker(db_ticker, db_news):
    # FIX Old code did assign everything to nasdaq :(
    try:
        full_symbol = db_ticker.full_symbol()

        rel_tickers = db_news.related_exchange_tickers
        if full_symbol not in rel_tickers:
            try:
                rel_tickers.remove("NASDAQ:" + db_ticker.ticker)  # PATCH FORCE REMOVE NASDAQ WRONG TICKER
            except:
                pass

            rel_tickers.append(full_symbol)
            db_news.update(**{'related_exchange_tickers': rel_tickers})

    except Exception as e:
        print_exception(e, "CRASHED FIXING NEWS")


def yticker_pipeline_process(db_ticker, dry_run=False):
    """
        Our fetching pipeline will call different status
    """
    from api.company.routes import api_create_ai_summary
    from api.news.routes import api_create_article_ai_summary
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
    ticker_save_financials(db_ticker.full_symbol(), yf_obj)

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
            update = False
            db_news = DB_News.objects(external_uuid=item['uuid']).first()
            if db_news:

                # We don't update news that we already have in the system
                #print_b(" ALREADY INDEXED ")
                update = True

                if not db_news.source_title:
                    db_news.update(**{'source_title': item['title']})

                try:
                    api_create_article_ai_summary(db_news)

                    fix_news_ticker(db_ticker, db_news)
                except Exception as e:
                    print_exception(e, "CRASHED")
                    pass

                continue

            print_b(" PROCESS " + item['link'])

            raw_data_id = 0
            try:
                # It should go to disk or something, this is madness to save it on the DB

                news_data = DB_DynamicNewsRawData(**item)
                news_data.save()
                raw_data_id = str(news_data['id'])
            except Exception as e:
                print_exception(e, "SAVE RAW DATA")

            new_schema = {
                'source_title': 'title',
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
                yticker_check_tickers(item['relatedTickers'])

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

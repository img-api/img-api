import json
import os
import re
from datetime import datetime, timedelta

import pandas as pd
import requests
import requests_cache
from api.company.routes import api_create_ai_summary
from api.news.models import DB_DynamicNewsRawData, DB_News
from api.news.routes import api_create_article_ai_summary
from api.print_helper import *
from api.query_helper import *
from api.query_helper import copy_replace_schema
from api.ticker.batch.yfinance.yfinance_news import yfetch_process_news
from api.ticker.connector_yfinance import fetch_tickers_info
from api.ticker.models import (DB_Ticker, DB_TickerHistoryTS, DB_TickerSimple,
                               DB_TickerTimeSeries)
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


def ticker_update_financials(full_symbol, max_age_minutes=15, force=False):
    """ This is a very slow ticker fetch system, we use yfinance here
        But we could call any of the other APIs

        Our ticker time will be delayed 15 minutes + whatever yahoo wants to give us.
        We don't want to hammer the service
    """
    from api.ticker.routes import ticker_get_history_date_days

    fin = DB_TickerSimple.objects(exchange_ticker=full_symbol).first()

    if not force and fin and fin.age_minutes() < max_age_minutes:
        fin['age_min'] = fin.age_minutes()
        return fin

    try:
        yticker = standardize_ticker_format_to_yfinance(full_symbol)
        yf_obj = fetch_tickers_info(yticker, no_cache=True)
        if not yf_obj:
            return fin

        new_schema = {
            'company_name': 'longName',
            'price': 'currentPrice',
            'ratio': 'currentRatio',
            'trailingEps': 'trailingEps',
            'day_low': 'dayLow',
            'day_high': 'dayHigh',
            'current_open': 'open',
            'previous_close': 'previousClose',
            'volume': 'volume',
            'bid': 'bid',
            'bid_size': 'bidSize',
        }

        try:
            if not yf_obj.info:
                print_r(full_symbol + " FAILED TO DOWNLOAD INFO ")
                return fin
        except Exception as e:
            print_exception(e, "CRASH")
            return fin

        fdata = prepare_update_with_schema(yf_obj.info, new_schema)
        ticker_save_financials(full_symbol, yf_obj)
        #ticker_save_history(full_symbol, yf_obj)

        if 'trailingEps' in fdata and fdata['trailingEps']:
            PE = round(fdata['price'] / fdata['trailingEps'], 2)
            fdata['PE'] = PE

        fdata['exchange_ticker'] = full_symbol

        # We try to check

        if fdata['day_high'] :
            try:
                if 'price' in fdata and fdata['previous_close']:
                    fdata['change_pct_1'] = round(
                        ((fdata['price'] - fdata['previous_close']) / fdata['previous_close']) * 100, 2)
            except Exception as e:
                pass
                #print_exception(e, "Crashed trying to load historical data")

            if fin and fin.historical_age_minutes() > 60 * 12:
                list_days = "8,15,31,365".split(',')
                for test in list_days:
                    try:
                        res = ticker_get_history_date_days(full_symbol, int(test))
                        if res:
                            change = ((fdata['day_high'] - res['close']) / res['close']) * 100
                            fdata['change_pct_' + str(test)] = round(change, 2)
                    except Exception as e:
                        print_exception(e, "Crashed trying to load historical data")

                fdata['last_history_update'] = datetime.now()
        if not fin:
            fin = DB_TickerSimple(**fdata)
            fin.save(validate=False)
        else:
            fin.update(**fdata, validate=False)

    except Exception as e:
        print_exception(e, "CRASH")

    return fin


def ticker_save_history(full_symbol, yf_obj, ts_interval="1d"):
    """ Test to capture 1 year of this ticker in intervals of 1 month for our basic graphs

    period: data period to download (either use period parameter or use start and end) Valid periods are:
        “1d”, “5d”, “1mo”, “3mo”, “6mo”, “1y”, “2y”, “5y”, “10y”, “ytd”, “max”

    interval: data interval (1m data is only for available for last 7 days, and data interval <1d for the last 60 days) Valid intervals are:
        “1m”, “2m”, “5m”, “15m”, “30m”, “60m”, “90m”, “1h”, “1d”, “5d”, “1wk”, “1mo”, “3mo”

    """

    from dateutil.relativedelta import relativedelta
    today = datetime.now()

    fin = DB_TickerHistoryTS.objects(exchange_ticker=full_symbol).order_by('-creation_date').limit(1).first()
    if fin and fin.age_days() < 2:
        print_r(full_symbol + " Too close ")
        return

    if fin:
        start = fin.creation_date.strftime("%Y-%m-%d")
    else:
        old_data_date = today - relativedelta(years=10)
        start = old_data_date.strftime("%Y-%m-%d")

    end = today.strftime("%Y-%m-%d")
    try:
        historical_data = yf_obj.history(start=start, end=end, interval=ts_interval)
        #print(historical_data)

        for index, row in historical_data.iterrows():
            #print(
            #    f"Date: {index} - Open: {row['Open']}, High: {row['High']}, Low: {row['Low']}, Close: {row['Close']}, Volume: {row['Volume']}"
            #)

            historical_ts = {
                'open': 'Open',
                'close': 'Close',
                'low': 'Low',
                'high': 'High',
                'volume': 'Volume',
                'stock_splits': 'Stock Splits',
                'dividends': 'Dividends',
            }

            hdata = prepare_update_with_schema(row, historical_ts)
            hdata['exchange_ticker'] = full_symbol
            hdata['creation_date'] = index

            # Historical yahoo finance and not current data
            hdata['source'] = 'HYF'

            fin = DB_TickerHistoryTS(**hdata)
            fin.save(validate=False)

    except Exception as e:
        print_exception(e, "CRASHED SAVING FINANCIALS ")
        return None


def ticker_save_financials(full_symbol, yf_obj, max_age_minutes=5):
    """ This is a very slow ticker fetch system, we use yfinance here
        But we could call any of the other APIs
    """
    try:

        internal_ticker_data_schema = {
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

        fin = DB_TickerTimeSeries.objects(exchange_ticker=full_symbol).order_by("-creation_date").limit(1).first()

        if fin and fin.age_minutes() < max_age_minutes:
            return fin

        if not yf_obj or not yf_obj.info:
            return

        if 'currentPrice' not in yf_obj.info:
            return

        if not yf_obj.info['currentPrice']:
            return fin

        fdata = prepare_update_with_schema(yf_obj.info, internal_ticker_data_schema)
        fdata['exchange_ticker'] = full_symbol

        fin = DB_TickerTimeSeries(**fdata)
        fin.save(validate=False)

        return fin

    except Exception as e:
        print_exception(e, "CRASHED SAVING FINANCIALS ")
        return None


def yticker_check_tickers(relatedTickers, item=None):
    from api.ticker.tickers_fetches import create_or_update_company

    try:
        result = []
        for local_ticker in relatedTickers:

            if '.' in local_ticker:
                print(" DEBUG ")

            query = DB_Ticker.query_exchange_ticker(local_ticker)
            db_ticker = DB_Ticker.objects(query).first()
            if db_ticker:
                result.append(db_ticker.full_symbol())
                continue

            yticker = standardize_ticker_format_to_yfinance(local_ticker)
            yf_obj = fetch_tickers_info(yticker, no_cache=True)
            if not yf_obj:
                continue

            info = yf_obj.info
            if not info:
                print_r(" NO Info fould for ticker? ")
                return

            if 'symbol' not in info:
                print_r(" No ticker? ")
                return

            if 'symbol' in info:
                ticker = info['symbol']
            else:
                ticker = ""

            if 'exchange' in info:
                exchange = info['exchange']
            else:
                exchange = ""

            if 'longName' in info:
                my_company = info['longName']
            else:
                my_company = ""

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

            et = db_company.exchange_tickers[-1]
            if et not in result:
                result.append(et)

        if item:
            item.update(**{'related_exchange_tickers': result})

    except Exception as e:
        print_exception(e, "CRASHED FINDING NEW TICKERS")
        return None

    return result


"""
    related_tickers = []
    for ticker in relatedTickers:

        ticker = standardize_ticker_format(ticker)
        exchange, ticker = ticker.split(":")

        candidates = DB_Company.objects(exchange_tickers__iendswith=":" + ticker)
        if len(candidates) == 0:
            print_r(ticker + " FAILED TO FIND COMPANY ")
        else:
            new_et = candidates.first().get_primary_ticker()
            if new_et not in related_tickers:
                related_tickers.append(new_et)

    print(str(related_tickers))
    if item:
        item.update(**{'related_exchange_tickers': related_tickers})

"""


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


def yticker_process_yahoo_news_article(item, info, ticker=None):
    update = False

    external_id = None
    if 'uuid' in item: external_id = item['uuid']
    if 'id' in item: external_id = item['id']

    # HACK sometimes the content is inside a content structure? wtf
    if 'content' in item:
        item = item['content']

    # Sometimes we get news that they don't have a list of tickers, but we know the ticker
    # Since we called explicitely their API for news for a particular company.
    # We append or force it to be our tickers.

    if ticker:
        if 'relatedTickers' not in item:
            item['relatedTickers'] = [ticker]
        elif ticker not in item['relatedTickers']:
            item['relatedTickers'].append(ticker)

    # Sometimes the External ID is an ID, sometimes a uuid...
    # We will probably have problems with this eventually.

    if external_id:
        db_news = DB_News.objects(external_uuid=external_id).first()
        if db_news:
            # We don't update news that we already have in the system
            #print_b(" ALREADY INDEXED ")
            update = True

            if not db_news.source_title:
                db_news.update(**{'source_title': item['title']})

            api_create_article_ai_summary(db_news)
            if 'raw_tickers' not in db_news and 'relatedTickers' in item:
                db_news.update(**{'raw_tickers': item['relatedTickers']})

            return

    raw_data_id = 0
    try:
        # It should go to disk or something, this is madness to save it on the DB

        if 'id' in item:
            del item['id']

        news_data = DB_DynamicNewsRawData(**item)
        news_data.save()
        raw_data_id = str(news_data['id'])
    except Exception as e:
        print_exception(e, "SAVE RAW DATA")

    if 'link' in item:
        print_b(" PROCESS " + item['link'])
        new_schema = {
            'source_title': 'title',
            'link': 'link',
            'external_uuid': 'uuid',
            'publisher': 'publisher',
            'summary': 'summary',
            'related_exchange_tickers': 'relatedTickers',
        }

        myupdate = prepare_update_with_schema(item, new_schema)
    else:
        print_r(" NO LINK ")
        myupdate = {
            'title': item['title'],
            'summary': item['summary'],
            'link': item['canonicalUrl']['url'],
            'publisher': item['provider']['displayName'],
            'thumbnail': item['thumbnail']['originalUrl'],
            'external_uuid': external_id,
            'thumbnail_caption': item['thumbnail']['caption'],
        }

    # Overwrite our creation time with the publisher time
    try:
        if 'relatedTickers' in item:
            rt = item['relatedTickers']
            myupdate['raw_tickers'] = rt
            yticker_check_tickers(rt, myupdate)

        if 'providerPublishTime' in item:
            value = datetime.fromtimestamp(int(item['providerPublishTime']))
            print_b(" DATE " + str(value))
            myupdate['creation_date'] = value

    except Exception as e:
        print_exception(e, "CRASHED LOADING DATE")

    try:
        if info and 'currentPrice' in info:
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


yahoo_company_schema = {
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
    'quote_type': 'quoteType',
    'gics_sub_industry': 'industry',
}


def yticker_pipeline_company_process(db_company):
    if not db_company:
        return None

    full_symbol = db_company.get_primary_ticker()

    yticker = standardize_ticker_format_to_yfinance(full_symbol)
    yf_obj = fetch_tickers_info(yticker, no_cache=True)
    try:
        api_create_ai_summary(db_company)
    except Exception as e:
        print_exception(e, "CRASH")
        pass

    info = yf_obj.info

    company_update = prepare_update_with_schema(info, yahoo_company_schema)

    if not company_update['long_name'] and 'shortName' in info:
        company_update['long_name'] = info['shortName']

    ticker_save_financials(full_symbol, yf_obj)
    ticker_save_history(full_symbol, yf_obj)

    if 'companyOfficers' in info:
        company_officers = info['companyOfficers']
        #for officer in company_officers:
        #    print_b(f"TODO: Create person {officer['name']} => {officer['title']}")

    if not 'ai_summary' in db_company:
        db_company.update(**company_update, validate=False)

    for item in yf_obj.news:
        try:
            yticker_process_yahoo_news_article(item, info, ticker=full_symbol)
        except Exception as e:
            print_exception(e, "CRASHED")


def yticker_pipeline_process(db_ticker, dry_run=False):
    """
        Our fetching pipeline will call different status
    """

    #print_b("PROCESSING: " + db_ticker.full_symbol())

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
        print_exception(e, "CRASH")
        pass

    info = yf_obj.info
    company_update = prepare_update_with_schema(info, yahoo_company_schema)

    if not company_update['long_name'] and 'shortName' in info:
        company_update['long_name'] = info['shortName']

    ticker_save_financials(db_ticker.full_symbol(), yf_obj)
    ticker_save_history(db_ticker.full_symbol(), yf_obj)

    if 'companyOfficers' in info:
        company_officers = info['companyOfficers']
        #for officer in company_officers:
        #    print_b(f"TODO: Create person {officer['name']} => {officer['title']}")

    if not db_company:
        print_b("NO COMPANY WTF")
    elif not 'ai_summary' in db_company:
        db_company.update(**company_update, validate=False)

    for item in yf_obj.news:
        try:
            yticker_process_yahoo_news_article(item, yf_obj.info, ticker=db_company.get_primary_ticker())
        except Exception as e:
            print_exception(e, "CRASH ON YAHOO NEWS PROCESSING")

    db_ticker.set_state("PROCESSED")
    return db_ticker

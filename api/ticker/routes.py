import io

import os
import time
import ffmpeg
import validators
import pandas as pd

from datetime import datetime
from api.ticker import blueprint
from api.api_redis import api_rq

from api import get_response_formatted, get_response_error_formatted, api_key_or_login_required, api_key_login_or_anonymous, cache
from flask import jsonify, request, send_file, redirect

from flask import current_app, url_for, abort
from api.print_helper import *

from api.tools import generate_file_md5, ensure_dir, is_api_call
from api.user.routes import generate_random_user
from .models import DB_Ticker, DB_TickerSimple, DB_TickerHighRes, DB_TickerUserWatchlist

from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q
from api.query_helper import mongo_to_dict_helper, build_query_from_request

from api.ticker.batch.tickers_pipeline import ticker_update_financials
from api.ticker.batch.workflow import ticker_process_batch, ticker_process_invalidate


@blueprint.route('/index/discovery', methods=['POST', 'GET'])
#@api_key_or_login_required
def api_index_fetch_and_process_tickers_list():
    """ It finds and indexes all the companies it can.

        It create all the tickers and adds them into the fetching process

        Creates all the companies,
        This is the stub test for a service to discover and capture tickers and companies
        To be divided into a discovery service.
    """
    from .tickers_fetches import process_all_tickers_and_symbols
    mylist = process_all_tickers_and_symbols()

    ret = {'processed': mylist}
    return get_response_formatted(ret)


@blueprint.route('/index/list', methods=['POST', 'GET'])
#@api_key_or_login_required
def api_index_fetch_tickers_list():
    from .tickers_fetches import get_all_tickers_and_symbols
    mylist = get_all_tickers_and_symbols()

    ret = {'suggestions': mylist}
    return get_response_formatted(ret)


@blueprint.route('/index/batch/dry_run', methods=['GET', 'POST'])
#@api_key_or_login_required
def api_batch_dry_run():
    """ We call the coordinator to process a batch of N tickers.
        We don't store any value, this is a testing / development call.
        This will call all the tickers that are older than
        the configured date and download news, information, process videos, etc.
    """

    processed = ticker_process_batch(dry_run=True)
    return get_response_formatted({'processed': processed})


@blueprint.route('/index/batch/process', methods=['GET', 'POST'])
#@api_key_or_login_required
def api_batch_process():
    """ We call the coordinator to process a batch of N tickers.

        We update the ticker, create all the orders to fetch news sites
        Call AI and get results.

        This will call all the tickers that are older than
        the configured date and download news, information, process videos, etc.

        This should go into a crontab / process coordinator
    """

    processed = ticker_process_batch(dry_run=False)
    return get_response_formatted({'processed': processed})


@blueprint.route('/<string:ticker>/update', methods=['GET', 'POST'])
#@api_key_or_login_required
def api_update_ticker(ticker):
    """ We invalidate a ticker so we load everything.
    """

    processed = ticker_process_invalidate(ticker)
    return get_response_formatted({'processed': processed})


@blueprint.route('/suggestions', methods=['GET', 'POST'])
#@api_key_or_login_required
def api_get_suggestions():
    from itertools import chain

    from .tickers_fetches import get_all_tickers_and_symbols
    from api.company.routes import company_get_suggestions

    query = request.args.get("query", "").upper()
    if not query:
        ret = {'status': 'success', 'suggestions': []}
        return get_response_formatted(ret)

    tickers = company_get_suggestions(query, only_tickers=True)

    db_tickers = DB_Ticker.objects(ticker__istartswith=query)
    filtered_recommendations = [rec.exchg_tick() for rec in db_tickers]

    #global_symbols = get_all_tickers_and_symbols()
    #filtered_recommendations = [rec for rec in global_symbols if query in rec]

    merged_list = list(chain(tickers, filtered_recommendations))
    unique_list = list(set(merged_list))

    if len(query) >= 2:
        print_b(" FORCE UPDATE ON THE LIST ")

        for rec in db_tickers:
            rec.reindex()

    ret = {'status': 'success', 'suggestions': unique_list}
    return get_response_formatted(ret)


@blueprint.route('/query', methods=['GET', 'POST'])
@api_key_or_login_required
def api_get_query():
    from flask_login import current_user
    """
    """

    tickers = build_query_from_request(DB_Ticker)

    ret = {'status': 'success', 'tickers': tickers}
    return get_response_formatted(ret)


@blueprint.route('/<string:ticker_id>/get', methods=['GET', 'POST'])
@api_key_or_login_required
def api_get_ticker(ticker_id):
    from flask_login import current_user
    """
    """

    if ticker_id == "all":
        if current_user.username == "admin":
            tickers = DB_Ticker.objects()
        else:
            tickers = DB_Ticker.objects(username=current_user.username)

        ret = {'status': 'success', 'ticker_id': ticker_id, 'tickers': tickers}
        return get_response_formatted(ret)

    q = Q(username=current_user.username) & Q(id=ticker_id)
    ticker = DB_Ticker.objects(q).first()

    ret = {'status': 'success', 'ticker_id': ticker_id, 'ticker': ticker}
    return get_response_formatted(ret)


@blueprint.route('/<string:ticker_id>/set/<string:my_key>', methods=['GET', 'POST'])
@api_key_or_login_required
def api_set_ticker_key(ticker_id, my_key):
    from flask_login import current_user  # Required by pytest, otherwise client crashes on CI

    ticker = DB_Ticker.objects(id=ticker_id).first()

    if not ticker:
        return get_response_error_formatted(404, {'error_msg': "Missing."})

    if not ticker.is_current_user():
        return get_response_error_formatted(403, {'error_msg': "This user is not allowed to perform this action."})

    value = request.args.get("value", None)
    if not value:
        if hasattr(request, "json") and 'value' in request.json:
            value = request.json['value']

    if value == None:
        return get_response_error_formatted(400, {'error_msg': "Wrong parameters."})

    value = clean_html(value)
    ticker.set_key_value(my_key, value)

    ret = {'status': 'success', 'ticker_id': ticker_id, 'ticker': ticker}
    return get_response_formatted(ret)


@blueprint.route('/<string:ticker_id>/rm', methods=['GET', 'POST'])
@api_key_or_login_required
def api_remove_ticker(ticker_id):
    from flask_login import current_user
    """
    """

    if ticker_id == "all":
        if current_user.username == "admin":
            tickers = DB_Ticker.objects()
        else:
            tickers = DB_Ticker.objects(username=current_user.username)

        tickers.delete()
        ret = {'status': 'success', 'ticker_id': ticker_id, 'tickers': tickers}
        return get_response_formatted(ret)

    q = Q(username=current_user.username) & Q(id=ticker_id)
    ticker = DB_Ticker.objects(q).first()
    ticker.delete()

    ret = {'status': 'success', 'ticker_id': ticker_id, 'ticker': ticker}
    return get_response_formatted(ret)


@blueprint.route('/create', methods=['POST'])
@api_key_or_login_required
def api_create_ticker():
    from flask_login import current_user

    if (ctype := request.headers.get('Content-Type')) != 'application/json':
        return get_response_error_formatted(400, {'error_msg': "Wrong call."})

    json_ = request.json

    ticker = DB_Ticker(**json_)
    ticker.save(validate=False)

    ret = {'status': 'success', 'ticker': mongo_to_dict_helper(ticker)}
    return get_response_formatted(ret)


@blueprint.route('/index/unit_test', methods=['POST', 'GET'])
#@api_key_or_login_required
def api_index_unit_test_tickers():
    from .tickers_helpers import tickers_unit_test
    return get_response_formatted(tickers_unit_test())


@blueprint.route('/exchange/get_long/<string:name>', methods=['POST', 'GET'])
#@api_key_or_login_required
def api_get_exchange_verbose_long_name(name):
    """ Returns a long name for the exchange so we can display it nicely """
    from .tickers_helpers import get_exchange_verbose
    return get_response_formatted({"exchange": name, "exchange_long_name": get_exchange_verbose(name)})


@blueprint.route('/index/test', methods=['POST', 'GET'])
#@api_key_or_login_required
def api_index_test_tickers():
    from .connector_yfinance import fetch_tickers_list

    tickers = ['NVO', 'QCOM']

    ticker_prices = fetch_tickers_list(tickers, period='1d', interval='1m')

    for ticker in tickers:
        print(f"{ticker}")

        data = ticker_prices[ticker]
        data.reset_index(inplace=True)

        print(data.head())

        data = data[['Datetime', 'Open', 'Low', 'High', 'Close', 'Volume']]

        # High frequency

        is_indexed = DB_TickerHighRes.objects(ticker=ticker, start=value[0])

        for value in data.values:
            mdict = {
                'ticker': ticker,
                'start': value[0],
                'end': value[0] + pd.Timedelta(minutes=1),
                'open': value[1],
                'low': value[2],
                'high': value[3],
                'close': value[4],
                'volume': value[5],
            }

            ticker_1m = DB_TickerHighRes(**mdict)
            ticker_1m.save(validate=False)

    ret = {'ticker': mongo_to_dict_helper(ticker)}
    return get_response_formatted(ret)


@blueprint.route('/get_info', methods=['POST', 'GET'])
#@api_key_or_login_required
def api_get_info_ticker():
    from .connector_yfinance import fetch_tickers_info

    ticker_name = request.args.get("ticker", None)

    ticker = fetch_tickers_info(ticker_name, no_cache=True)

    ret = {
        'status': 'success',
        'ticker': ticker_name,
        'info': ticker.info,
        'news': ticker.news,
        'options': ticker.options
    }
    return get_response_formatted(ret)


@blueprint.route('/rm/<string:ticker_id>', methods=['GET', 'POST'])
@blueprint.route('/remove/<string:ticker_id>', methods=['GET', 'POST'])
# TODO: CHECK API ONLY ADMIN
def api_remove_a_ticker_by_id(ticker_id):
    """
    """

    if ticker_id == "ALL":
        DB_Ticker.objects().delete()
        ret = {'status': "deleted"}
        return get_response_formatted(ret)

    db_ticker = DB_Ticker.objects(id=ticker_id).first()

    if not db_ticker:
        return get_response_error_formatted(404, "Ticker not found")

    db_ticker.delete()
    return get_response_formatted({'status': "deleted"})


##########################################################################
# An user watchlist is a list of tickers in the format EXCHANGE:TICKER


def get_watchlist_or_create(name):
    from flask_login import current_user

    watchlist = DB_TickerUserWatchlist.objects(username=current_user.username, list_name=name).first()
    if watchlist:
        return watchlist

    new_list = {"username": current_user.username, "list_name": name}

    watchlist = DB_TickerUserWatchlist(**new_list)
    watchlist.save(validate=False)
    return watchlist


@blueprint.route('/user/watchlist/rm/<string:name>', methods=['GET', 'POST'])
@api_key_or_login_required
def api_user_watchlist_delete(name):
    """
        Returns a list of tickers that the user is watching.
    """
    from flask_login import current_user

    watchlist = get_watchlist_or_create(name)
    DB_TickerUserWatchlist.objects(username=current_user.username, list_name=name).delete()

    ret = {"deleted": name}
    return get_response_formatted(ret)


@blueprint.route('/user/watchlist/get/<string:name>', methods=['GET', 'POST'])
@api_key_or_login_required
def api_user_watchlist(name):
    """
        Returns a list of tickers that the user is watching.
    """

    watchlist = get_watchlist_or_create(name)
    ret = {'list_name': name, 'exchange_tickers': watchlist.exchange_tickers}

    if request.args.get("add_financials", None) == "1":
        fin = {}
        for full_symbol in watchlist.exchange_tickers:
            try:
                fin[full_symbol] = ticker_update_financials(full_symbol)
            except Exception as e:
                print_exception(e, "CRASHED FINANCIAL UPDATES")

        ret['financials'] = fin

    return get_response_formatted(ret)


@blueprint.route('/user/watchlist/<string:operation>/<string:name>/<string:exchange_ticker>', methods=['GET', 'POST'])
@api_key_or_login_required
def api_user_watchlist_operation(operation, name, exchange_ticker):
    from flask_login import current_user
    """ Operations on lists
    """

    watchlist = get_watchlist_or_create(name)

    if operation == "remove_ticker":
        if exchange_ticker in watchlist.exchange_tickers:
            watchlist.exchange_tickers.remove(exchange_ticker)
    else:
        if exchange_ticker not in watchlist.exchange_tickers:
            watchlist.exchange_tickers.append(exchange_ticker)

    watchlist.save()
    ret = {'list_name': name, 'exchange_tickers': watchlist.exchange_tickers}
    return get_response_formatted(ret)

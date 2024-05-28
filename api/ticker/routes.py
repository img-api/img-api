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
from .models import DB_Ticker, DB_TickerSimple, DB_TickerHighRes

from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q
from api.query_helper import mongo_to_dict_helper, build_query_from_request


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


@blueprint.route('/index_test', methods=['POST', 'GET'])
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

    ret = {'status': 'success', 'ticker': mongo_to_dict_helper(ticker)}
    return get_response_formatted(ret)
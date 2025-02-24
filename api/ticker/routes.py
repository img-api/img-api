from datetime import datetime

import pandas as pd
from api import (admin_login_required, api_key_or_login_required, cache,
                 cache_make_key, get_response_error_formatted,
                 get_response_formatted)
from api.company.models import DB_Company
from api.file_cache import api_file_cache
from api.print_helper import *
from api.query_helper import (build_query_from_request, get_timestamp_verbose,
                              mongo_to_dict_helper)
from api.ticker import blueprint
from api.ticker.batch.workflow import (ticker_process_batch,
                                       ticker_process_invalidate,
                                       ticker_process_news_sites)
from api.ticker.batch.yfinance.ytickers_pipeline import \
    ticker_update_financials
from api.ticker.tickers_helpers import standardize_ticker_format
from flask import request
from flask_cachecontrol import ResponseIsSuccessfulOrRedirect, cache_for
from mongoengine.queryset.visitor import Q

from .models import (DB_Ticker, DB_TickerHighRes, DB_TickerHistoryTS,
                     DB_TickerSimple, DB_TickerTimeSeries,
                     DB_TickerUserWatchlist)


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


@blueprint.route('/index/batch/get_tickers', methods=['GET', 'POST'])
def api_get_ticker_process_batch(end=None, BATCH_SIZE=10):
    """
    Gets a list of tickers and calls the different APIs to capture and process the data.

    Limit to BATCH_SIZE so we don't ask for too many at once to all APIs
    """
    lte = request.args.get("lte", "1 hour")
    update = request.args.get("update", "true")
    BATCH_SIZE = int(request.args.get("limit", BATCH_SIZE))

    end = datetime.fromtimestamp(get_timestamp_verbose(lte))

    query = Q(force_reindex=True)
    tickers = DB_Ticker.objects(query)[:BATCH_SIZE]
    if tickers.count() == 0:
        #query = Q(last_processed_date__lte=end) | Q(last_processed_date=None)
        tickers = DB_Ticker.objects().order_by('+last_processed_date')[:BATCH_SIZE]

        for ticker in tickers:
            if update == "true":
                ticker.set_state("API_FETCHED")

            ticker['verbose_date'] = ticker.last_processed_date.strftime("%Y/%m/%d, %H:%M:%S")

    return get_response_formatted({'tickers': tickers})


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

    lte = request.args.get("lte", "1 hour")
    ts = get_timestamp_verbose(lte)
    print_b(" PROCESS => " + str(ts))

    end = datetime.fromtimestamp(ts)

    print_b(" PROCESS REAL DATE " + str(end))
    BATCH_SIZE = int(request.args.get("limit", 10))

    processed = ticker_process_batch(end, BATCH_SIZE=BATCH_SIZE)

    for p in processed:
        p['verbose_date'] = str(p['last_processed_date'])

    return get_response_formatted({'processed': processed})


@blueprint.route('/index/batch/process_news', methods=['GET', 'POST'])
def api_empty():
    client_ip = request.remote_addr
    print(str(client_ip))
    return get_response_formatted({})


@blueprint.route('/index/process_news', methods=['GET', 'POST'])
#@api_key_or_login_required
def api_batch_news_process():
    """
        Processes the links on the news folder, it will search for a batch of unprocess data and launch fetches
    """

    processed = ticker_process_news_sites()
    return get_response_formatted({'processed': processed})


@blueprint.route('/invalidate/<string:full_symbol>', methods=['GET', 'POST'])
@api_key_or_login_required
def api_update_ticker(full_symbol):
    """ We invalidate a ticker so we load everything.
    """
    from api.ticker.batch.workflow import ticker_process_invalidate_full_symbol
    from flask_login import current_user

    from .tickers_helpers import extract_ticker_from_symbol

    if not current_user.subscription or current_user.subscription.status != "active":
        return get_response_formatted({})

    ticker = extract_ticker_from_symbol(full_symbol)

    processed = ticker_process_invalidate(ticker)
    ticker_process_invalidate_full_symbol(full_symbol)
    return get_response_formatted({'processed': processed})


def get_full_symbol(ticker):
    """ Converts a ticker like NVO into NYE:NVO """

    db_ticker = DB_Ticker.objects(ticker=ticker).first()
    if db_ticker:
        ticker = db_ticker.full_symbol()

    return standardize_ticker_format(ticker)


@blueprint.route('/get_full_symbol/<string:ticker>', methods=['GET', 'POST'])
def api_find_full_symbol(ticker):
    """ We append NASDAQ or NSYE or whatever for a ticker"""

    full_symbol = get_full_symbol(ticker)
    return get_response_formatted({'full_symbol': full_symbol})


@blueprint.route('/suggestions', methods=['GET', 'POST'])
#@api_key_or_login_required
def api_get_suggestions():
    from itertools import chain

    from api.company.routes import company_get_suggestions

    query = request.args.get("query", "").upper()
    if not query:
        ret = {'status': 'success', 'suggestions': []}
        return get_response_formatted(ret)

    tickers = company_get_suggestions(query, only_tickers=True)

    db_tickers = DB_Ticker.objects(ticker__istartswith=query)
    filtered_recommendations = [rec.full_symbol() for rec in db_tickers]

    #global_symbols = get_all_tickers_and_symbols()
    #filtered_recommendations = [rec for rec in global_symbols if query in rec]

    merged_list = list(chain(tickers, filtered_recommendations))
    unique_list = list(set(merged_list))

    if len(query) >= 2:
        print_b(" FORCE UPDATE ON THE LIST ")

        for rec in db_tickers:
            rec.reindex()

    ret = {'suggestions': unique_list, "query": query}
    return get_response_formatted(ret)


@blueprint.route('/query', methods=['GET', 'POST'])
#@api_key_or_login_required
def api_get_query():
    """
    """

    tickers = build_query_from_request(DB_Ticker, global_api=True)

    ret = {'tickers': tickers}
    return get_response_formatted(ret)


@blueprint.route('/ts/query', methods=['GET', 'POST'])
@api_key_or_login_required
@api_file_cache(expiration_secs=3600)
def api_get_financial_query():
    """ https://domain/api/ticker/ts/query?id__exists=1&order_by=-creation_date
        http://domain/api/ticker/ts/query?exchange_ticker=NYSE:UNH&verbose=1
    """
    time_series = build_query_from_request(DB_TickerTimeSeries, global_api=True)

    verbose = request.args.get("verbose", None)

    ret = {'ts': time_series}
    return get_response_formatted(ret)


@blueprint.route('/<string:ticker_id>/get', methods=['GET', 'POST'])
@api_key_or_login_required
@cache.cached(timeout=300)
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
    from flask_login import \
        current_user  # Required by pytest, otherwise client crashes on CI

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
    pass

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


@blueprint.route('/index/unit_test/selenium', methods=['GET', 'POST'])
#@api_key_or_login_required
def api_test_if_selenium_and_chrome_works():
    """
    """
    from api.ticker.batch.html.selenium_integration import \
        selenium_integration_test

    test_result = selenium_integration_test()
    return get_response_formatted({'test_is_successful': test_result})


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


@blueprint.route('/get_price', methods=['POST', 'GET'])
#@api_key_or_login_required
def api_get_ticker_get_price():
    from .tickers_fetches import getPrices

    ticker_name = request.args.get("ticker", None)

    prices, income_statement, balance_sheet, cash_flow = getPrices(ticker_name)

    ret = {
        'status': 'success',
        'ticker': ticker_name,
        'income_statement': str(income_statement),
    }


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


def get_watchlist_or_create(name="default", username=None):
    from flask_login import current_user

    if not username:
        username = current_user.username

    watchlist = DB_TickerUserWatchlist.objects(username=username, list_name=name).first()
    if watchlist:
        return watchlist

    new_list = {"username": username, "list_name": name}

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
    """ Operations on lists
    """

    watchlist = get_watchlist_or_create(name)

    if operation == "remove_ticker" or operation == "remove":
        if exchange_ticker in watchlist.exchange_tickers:
            watchlist.exchange_tickers.remove(exchange_ticker)
    else:
        if exchange_ticker not in watchlist.exchange_tickers:
            watchlist.exchange_tickers.append(exchange_ticker)

    watchlist.save()
    ret = {'list_name': name, 'exchange_tickers': watchlist.exchange_tickers}
    return get_response_formatted(ret)


@blueprint.route("user/test", methods=["GET", "POST"])
def yahoo_test():
    from tickers_fetches import download_yahoo_news
    tickers = ["MSFT", "KO"]
    for ticker in tickers:
        try:
            download_yahoo_news(ticker)
        except Exception as e:
            print(e)


def get_yearly_change(exchange_ticker):
    pipeline = [
        # Step 1: Filter documents by exchange_ticker
        {
            '$match': {
                'exchange_ticker': exchange_ticker
            }
        },
        # Step 2: Add a year field by extracting the year from the creation_date
        {
            '$addFields': {
                'year': {
                    '$year': '$creation_date'
                }
            }
        },
        # Step 3: Group by year, getting the first and last closing prices
        {
            '$group': {
                '_id': '$year',  # Group by the extracted year
                'first_close': {
                    '$first': '$close'
                },  # First close of the year
                'last_close': {
                    '$last': '$close'
                },  # Last close of the year
            }
        },
        # Step 4: Calculate the yearly change (last - first close)
        {
            '$project': {
                '_id': 0,  # Remove the default _id field
                'year': '$_id',
                'yearly_change': {
                    '$subtract': ['$last_close', '$first_close']
                }
            }
        },
        # Step 5: Sort by year (ascending order)
        {
            '$sort': {
                'year': 1
            }
        }
    ]

    # Run the aggregation pipeline
    results = DB_TickerHistoryTS.objects.aggregate(pipeline)

    # Print or return the results

    ret = {}
    for result in results:
        print(f"Year: {result['year']}, Yearly Change: {result['yearly_change']}")
        ret[result['year']] = result['yearly_change']

    return ret


@blueprint.route('/history_change/<string:full_symbol>', methods=['GET', 'POST'])
def api_find_full_symbol_historical_change_data(full_symbol):
    return get_response_formatted({'exchange_ticker': full_symbol, 'results': get_yearly_change(full_symbol)})


@blueprint.route('/query/simple', methods=['GET', 'POST'])
@api_file_cache(expiration_secs=600)
def api_get_tickers():
    tickers = build_query_from_request(DB_TickerSimple, global_api=True)

    ret = {'tickers': tickers}
    return get_response_formatted(ret)


@blueprint.route('/history/<string:full_symbol>', methods=['GET', 'POST'])
@api_file_cache(expiration_secs=86400)
def api_find_full_symbol_historical_data(full_symbol):
    from api.query_helper import (mongo_to_dict_helper,
                                  prepare_update_with_schema)

    start_time = datetime.now()

    results = DB_TickerHistoryTS.objects(exchange_ticker=full_symbol).order_by("-creation_date")

    if request.args.get('verbose'):
        for ts in results:
            ts['creation_date_verbose'] = ts.creation_date.strftime("%Y/%m/%d, %H:%M:%S")

    fin = DB_TickerSimple.objects(exchange_ticker=full_symbol).first()
    if fin:
        res = mongo_to_dict_helper(results)
        new_schema = {
            "creation_date": "last_update",
            "open": "price",
            "close": "previous_close",
            "high": "day_high",
            "low": "day_low",
            "volume": "volume",
        }

        myupdate = prepare_update_with_schema(fin.serialize(), new_schema)
        res.append(myupdate)

        results = res

    end_time = (datetime.now() - start_time).total_seconds()
    print_g(" TOTAL TIME IN SECS " + str(end_time))

    return get_response_formatted({'exchange_ticker': full_symbol, 'results': results})


@blueprint.route('/history/empty', methods=['GET', 'POST'])
@api_key_or_login_required
@admin_login_required
def api_delete_allhistory():
    DB_TickerHistoryTS.objects().delete()
    return get_response_formatted({'status': 'deleted'})


@blueprint.route('/technical/crossovers', methods=['GET', 'POST'])
#@api_key_or_login_required
def api_detect_crossovers():

    exchange_ticker = request.args.get("exchange_ticker", None)

    pipeline = []

    if exchange_ticker:
        pipeline.append({'$match': {'exchange_ticker': exchange_ticker}})

        pipeline.append({"$sort": {"creation_date": 1}})
    else:
        # Sort documents by ticker symbol and creation_date
        sorting = {"$sort": {"exchange_ticker": 1, "creation_date": 1}}
        pipeline.append(sorting)

    # Calculate moving averages (50-day and 200-day)
    window = {
        "$setWindowFields": {
            "sortBy": {
                "creation_date": 1
            },
            "partitionBy": "$exchange_ticker",  # Group by ticker
            "output": {
                "ma50": {  # Equivalent to ~50-day moving average
                    "$avg": "$close",
                    "window": {
                        "documents": [-6, 0]
                    }
                },
                "ma200": {  # Equivalent to ~200-day moving average
                    "$avg": "$close",
                    "window": {
                        "documents": [-28, 0]
                    }
                }
            }
        }
    }

    pipeline.append(window)

    # Project relevant fields
    project = {
        "$project": {
            "exchange_ticker": 1,
            "close": 1,
            "creation_date": 1,
            "ma50": 1,
            "ma200": 1,
            "crossoverType": {
                "$switch": {
                    "branches": [
                        {  # Golden Cross: ma50 crosses above ma200
                            "case": {
                                "$and": [
                                    {
                                        "$gt": ["$ma50", "$ma200"]
                                    },
                                    {
                                        "$lt": ["$ma50", {
                                            "$avg": ["$ma200", -1]
                                        }]
                                    }  # Detect upward cross
                                ]
                            },
                            "then": "Golden Cross"
                        },
                        {  # Death Cross: ma50 crosses below ma200
                            "case": {
                                "$and": [
                                    {
                                        "$lt": ["$ma50", "$ma200"]
                                    },
                                    {
                                        "$gt": ["$ma50", {
                                            "$avg": ["$ma200", -1]
                                        }]
                                    }  # Detect downward cross
                                ]
                            },
                            "then": "Death Cross"
                        }
                    ],
                    "default":
                    "None"
                }
            }
        }
    }

    pipeline.append(project)

    # Sort results by date
    final_sort = {"$match": {"crossoverType": {"$in": ["Golden Cross", "Death Cross"]}}}

    #pipeline.append(final_sort)

    # Execute the aggregation pipeline
    results = DB_TickerHistoryTS.objects().aggregate(pipeline)

    return get_response_formatted({"crossovers": results})


def ticker_get_history_date_days(full_symbol, days):
    """
    """

    from dateutil.relativedelta import relativedelta
    time_frame_min = datetime.now() - relativedelta(days=days)

    # Our database has a 1 days maximum data frame.
    time_frame_max = datetime.now() - relativedelta(days=(days - 7))

    data = DB_TickerHistoryTS.objects(exchange_ticker=full_symbol,
                                      creation_date__lte=time_frame_max,
                                      creation_date__gte=time_frame_min).order_by('-creation_date').limit(1).first()

    if not data:
        print_r(f" { full_symbol } Failed range from { str(time_frame_min)[:10] } to { str(time_frame_max)[:10] }")
        data = DB_TickerHistoryTS.objects(
            exchange_ticker=full_symbol, creation_date__gte=time_frame_min).order_by('-creation_date').limit(1).first()

        if data:
            print_b(f" found later than min ")

    return data


@blueprint.route('/index/<string:symbol>', methods=['GET', 'POST'])
def api_index_new_ticker(symbol):
    from .batch.yfinance.ytickers_pipeline import (
        yticker_check_tickers, yticker_pipeline_company_process)

    ret = yticker_check_tickers([symbol], item=None)
    if not ret:
        return get_response_formatted({})

    for c in ret:
        if isinstance(c, DB_Company):
            yticker_pipeline_company_process(c)

    return get_response_formatted({"index": ret})


@blueprint.route('/forceindex', methods=['GET', 'POST'])
def api_forceindex():
    DB_TickerHistoryTS.create_index([('exchange_ticker', 1), ('creation_date', -1)])
    return get_response_formatted({"index": "DONE"})



@blueprint.route('/cleanup', methods=['GET', 'POST'])
def api_force_cleanup_duplicates():

    tickers = DB_Ticker.objects()

    dups = {}

    count = 0
    for t in tickers:
        if not t.ticker:
            t.delete()
            continue

        f = t.full_symbol()
        #print_b(f" PROCESS { f }")
        if f not in dups:
            dups[f] = [t]
            count += 1
        else:
            dups[f].append(t)

    deleted = 0
    for key, lst in dups.items():
        if len(lst) == 1:
            continue

        #print_r(f" DEDUPE { key }")
        candidate = None
        for i in lst:
            if candidate or not i.get_company():
                i.delete()
                deleted += 1
                continue

            candidate = i

    return get_response_formatted({"deleted": deleted, 'tickers': count})







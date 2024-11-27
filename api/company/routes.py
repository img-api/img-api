import binascii
import io
import random
import re
import time
from datetime import datetime

import bcrypt
import qrcode
import requests
import validators
from api import (api_key_login_or_anonymous, api_key_or_login_required, cache,
                 get_response_error_formatted, get_response_formatted)
from api.company import blueprint
from api.company.models import DB_Company, DB_CompanyPrompt
from api.print_helper import *
from api.query_helper import (build_query_from_request, get_timestamp_verbose,
                              is_mongo_id, mongo_to_dict_helper)
from api.tools.validators import get_validated_email
from flask import Response, abort, jsonify, redirect, request, send_file
from flask_login import current_user
from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q


@blueprint.route('/query', methods=['GET', 'POST'])
#@api_key_or_login_required
def api_company_get_query():
    """
    Example of queries: https://dev.gputop.com/api/company/query?founded=1994

    https://gputop.com/api/company/query?exchange_tickers=NASDAQ:INTC

    """

    companies = build_query_from_request(DB_Company, global_api=True)

    if len(companies) == 0:
        # Patch to fix issue with tickers that refer to the same company.
        query = request.args.get("exchange_tickers", None).upper()
        if '-' in query:
            arr = query.split('-')
            companies = DB_Company.objects(exchange_tickers=arr[0])

    ret = {'companies': companies}
    return get_response_formatted(ret)


def company_get_suggestions(text, only_tickers=False):
    """ """

    # Don't destroy the database
    if only_tickers and len(text) < 3:
        return []

    if len(text) > 3:
        query = Q(company_name__icontains=text)
    else:
        query = Q(company_name__istartswith=text)

    if len(text) <= 4:
        query = query | Q(exchange_tickers__icontains=text)

    companies = DB_Company.objects(query)

    if only_tickers:
        tickers = []
        for rec in companies:
            print(" Rec " + rec.company_name)
            for i in rec.exchange_tickers:
                tickers.append(i)

        return tickers

    return companies


@blueprint.route('/suggestions', methods=['GET', 'POST'])
#@api_key_or_login_required
def api_company_get_suggestions():
    """ """
    query = request.args.get("query", "").upper()
    if not query:
        ret = {'status': 'success', 'suggestions': []}
        return get_response_formatted(ret)

    suggs = company_get_suggestions(query)

    #extra = [{"company_name": rec.company_name, "exchange_tickers": rec.exchange_tickers} for rec in suggs]
    extra = [rec.exchange_tickers[0] for rec in suggs]

    suggestions = [rec.company_name for rec in suggs]
    ret = {'suggestions': suggestions, 'extra': extra, "query": query}
    return get_response_formatted(ret)


@blueprint.route('/create', methods=['GET', 'POST'])
#@api_key_or_login_required
def api_create_business_for_user_local():
    """ Business creation
    ---
    """

    print("======= CREATE Company Local =============")

    json = request.json
    business = DB_Company(**json)
    business.save()

    return get_response_formatted(business.serialize())


@blueprint.route('/rm/<string:biz_id>', methods=['GET', 'POST'])
@blueprint.route('/remove/<string:biz_id>', methods=['GET', 'POST'])
def api_remove_a_business_by_id(biz_id):
    """ Business deletion
    ---
    """

    # CHECK API ONLY ADMIN
    if biz_id == "ALL":
        DB_Company.objects().delete()
        ret = {'status': "deleted"}
        return get_response_formatted(ret)

    business = DB_Company.objects(id=biz_id).first()

    if not business:
        return get_response_error_formatted(404, {'error_msg': "Business not found for the current user"})

    ret = {'status': "deleted", 'company': business.serialize()}

    business.delete()
    return get_response_formatted(ret)


@blueprint.route('/get/<string:biz_name>', methods=['GET', 'POST'])
@blueprint.route('/get/<string:biz_name>', methods=['GET', 'POST'])
def api_get_business_info(biz_name):
    """ Business get info
    ---
    """
    if biz_name == "ALL":
        business = DB_Company.objects()

        result_array = [item.serialize() for item in business]
        ret = {'company': result_array}
        return get_response_formatted(ret)

    if is_mongo_id(biz_name):
        business = DB_Company.objects(id=biz_name).first()
    else:
        business = DB_Company.objects(safe_name=biz_name).first()

    if not business:
        return get_response_error_formatted(404, {'error_msg': "Business not found"})

    ret = {'company': business.serialize()}
    return get_response_formatted(ret)


@blueprint.route('/get_stamp/<string:biz_name>', methods=['GET', 'POST'])
def api_get_new_stamp(biz_name):
    """ Business get new stamp
    ---
    """

    from cryptography.fernet import Fernet

    business = DB_Company.objects(safe_name=biz_name).first()

    if not business:
        return get_response_error_formatted(404, {'error_msg': "Business not found"})

    stamp = business.get_new_stamp()
    content = request.url_root + "api/biz/stamp/" + biz_name + "/" + stamp

    print(content)

    img = qrcode.make(content)
    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)
    return send_file(buf, mimetype='image/jpeg')


@blueprint.route('/stamp/<string:biz_name>/<string:encrypted_date>', methods=['GET', 'POST'])
def api_apply_stamp(biz_name, encrypted_date):
    """ Business stamp an user
    ---
    """

    business = DB_Company.objects(safe_name=biz_name).first()

    if not business:
        return get_response_error_formatted(404, {'error_msg': "Business not found"})

    stamp = business.decode_stamp(encrypted_date)

    ret = {
        'result': "OK",
        'stamp_age_sec': stamp,
        'company': business.serialize(),
    }

    if stamp > 300:
        ret['result'] = "EXPIRED STAMP"

        ret.update({'error_msg': "Stamp expired and is GONE"})
        return get_response_error_formatted(410, ret)

    # Find user if there is an user

    # Increment the stamps amount

    #

    return get_response_formatted(ret)


@blueprint.route('/categories', methods=['GET', 'POST'])
def company_explorer_categories():
    """
        Examples, you can search for a gics_sector or group by category and industry.
        /api/company/categories?gics_sector=Basic%20Materials&group=gics_sub_industry
    """
    exchange = request.args.get("exchange", "").upper()
    group = request.args.get("group", "gics_sector")

    gics_sector = request.args.get("gics_sector", None)

    pipeline = []
    if gics_sector:
        match_exchange = {
            "$match": {
                "gics_sector": gics_sector,
            }
        }

        pipeline.append(match_exchange)

    elif exchange:
        match_exchange = {
            "$match": {
                "exchanges": exchange,
            }
        }

        pipeline.append(match_exchange)

    pipeline.append({"$group": {"_id": "$" + group, "count": {"$sum": 1}}})
    pipeline.append({"$sort": {"_id": 1}})

    ret = {}

    ret['result'] = list(DB_Company.objects.aggregate(*pipeline))
    ret['pipeline'] = [pipeline]

    return get_response_formatted(ret)


def api_create_ai_summary(company, force_summary=False):
    prompt = "Summarize this, and format it max one paragraph and 5 bullet points, use markdown to highlight important facts: "

    if not company['long_business_summary']:
        return

    if not force_summary and 'ai_summary' in company or 'ia_summary' in company:
        return

    age_update = (datetime.now() - company.ai_upload_date).total_seconds() / 60
    if age_update < 600:
        return

    data = {
        'type': 'summary',
        'id': company['safe_name'],
        'message': prompt + company['long_business_summary'],
        'callback_url': "https://tothemoon.life/api/company/ai_callback"
    }

    print_b(" INDEX " + company['safe_name'])
    response = requests.post("https://lachati.com/api_v1/upload-json", json=data)
    response.raise_for_status()

    company.update({'ai_upload_date': datetime.now()})


@blueprint.route('/ai_summary', methods=['GET', 'POST'])
#@api_key_or_login_required
def api_company_get_ai_summary():
    """
        https://gputop.com/api/company/ai_summary?exchange_tickers=NASDAQ:INTC

    """
    index_all = request.args.get("index_all", None)

    if index_all:
        companies = DB_Company.objects()
    else:
        companies = build_query_from_request(DB_Company, global_api=True)

    for company in companies:
        api_create_ai_summary(company, True)

    ret = {'companies': companies}
    return get_response_formatted(ret)


@blueprint.route('/ai_callback', methods=['GET', 'POST'])
#@api_key_or_login_required
def api_company_callback_ai_summary():
    """ """
    json = request.json

    business = DB_Company.objects(safe_name=json['id']).first()

    if 'type' in json:

        print_b(" AI_CALLBACK " + json['id'])

        t = json['type']
        if t == 'dict':
            functions = {'tools': json['dict']}
            business.update(**functions)
        elif t == 'summary':
            if 'result' in json:
                business.set_key_value('ai_summary', json['result'])

    ret = {}
    return get_response_formatted(ret)


@blueprint.route('/get_related/<string:full_ticker>', methods=['GET', 'POST'])
#@api_key_or_login_required
def api_group_news_query(full_ticker):
    from api.news.models import DB_News

    lte = request.args.get("gte", "2 months")
    limit = int(request.args.get("limit", "25"))
    end = datetime.fromtimestamp(get_timestamp_verbose(lte))

    pipeline = [
        # Step 1: Match documents based on creation_date and related_exchange_tickers array contents
        {
            "$match": {
                "creation_date": {
                    "$gte": end
                },
                "related_exchange_tickers": {
                    "$in": [full_ticker]
                },
            }
        },
        # Step 2: Unwind the related_exchange_tickers array to process each ticker individually
        {
            "$unwind": "$related_exchange_tickers"
        },
        # Step 3: Group by each ticker and count occurrences
        {
            "$group": {
                "_id": "$related_exchange_tickers",  # Group by each ticker
                "count": {
                    "$sum": 1
                }  # Count each occurrence
            }
        }
    ]

    data = list(DB_News.objects.aggregate(*pipeline))

    sorted_data_tuples = [(item["_id"], item["count"]) for item in sorted(data, key=lambda x: x['count'], reverse=True)]

    check = [item[0] for item in sorted_data_tuples[0:limit]]
    check_pipeline = [{
        "$match": {
            "exchange_tickers": {
                "$in": check
            },
        },
    }, {
        "$project": {
            "_id": 0,
            "company_name": 1,
            "exchange_tickers": 1,
        }
    }]

    valid_tickers = list(DB_Company.objects.aggregate(*check_pipeline))

    # Create a dictionary to map tickers to their counts
    ticker_count_dict = {ticker: count for ticker, count in sorted_data_tuples}

    if full_ticker in ticker_count_dict:
        del ticker_count_dict[full_ticker]

    # Sort related_companies by count based on the exchange_tickers in the result
    sorted_companies = sorted(
        valid_tickers,
        key=lambda company: sum(ticker_count_dict.get(ticker, 0) for ticker in company["exchange_tickers"]),
        reverse=True)

    ret = {'result': sorted_data_tuples, 'pipeline': pipeline, 'related_companies': sorted_companies}

    return get_response_formatted(ret)


@blueprint.route('/invalidate/<string:company_id>', methods=['GET', 'POST'])
def api_update_company(company_id):
    """ We refetch a company
    """
    from api.ticker.batch.workflow import ticker_process_invalidate_full_symbol
    from api.ticker.tickers_fetches import create_or_update_ticker

    db_company = DB_Company.objects(id=company_id).first()
    if not db_company or not db_company.exchange_tickers:
        return get_response_error_formatted(404, {'error_msg': "Business doesn't have tickers!"})

    ticker = db_company.exchange_tickers[-1]
    processed = ticker_process_invalidate_full_symbol(ticker)

    return get_response_formatted({'processed': processed})


def api_build_company_state_query(db_company):
    from api.news.routes import get_portfolio_query

    content = ""
    news, tkrs = get_portfolio_query(tickers_list=db_company.exchange_tickers)

    if not news:
        return

    unique_tickers = set()

    for index, article in enumerate(news):
        unique_tickers = set(article.related_exchange_tickers) | unique_tickers
        content += "| Article " + str(index) + " from " + article.publisher + "\n"
        content += "| Title: " + article.get_title() + "\n"
        content += article.get_summary()[:64] + "\n"
        content += "\n---\n"

    #tickers = str.join(",", unique_tickers)
    #content += "## Tickers: " + tickers + "\n\n"

    prompt = "Given the articles for "
    prompt += db_company.long_name
    prompt += "What is the current state of the company ?"

    system = "Analyze the provided articles to assess the performance of the company mentioned and its potential impact on stock market trends. Focus on the following aspects:"
    system += "Company Performance:"
    #system += "Financial metrics (revenue, profit, losses, etc.)."
    system += "Recent achievements, product launches, or innovations."
    system += "Management decisions, leadership changes, or strategic announcements."
    system += "Any risks, challenges, or controversies highlighted."
    system += "Market Sentiment:"
    system += "Extract and summarize the tone of the article (positive, neutral, or negative)."
    system += "Identify any indications of market confidence or concerns about the company."
    system += "Note mentions of investor behavior or reactions."
    system += "Industry and Market Impact:"
    system += "Discuss the company's position within its industry."
    system += "Highlight any trends or competitive dynamics affecting the company."
    system += "Note how broader market conditions (e.g., interest rates, geopolitical events) are influencing its performance."
    system += "Future Outlook:"
    system += "Identify predictions or expectations about the company or its stock."
    system += "Summarize any analyst opinions or forecasts."
    system += "Highlight any plans or milestones mentioned that could affect future performance."
    system += "Provide a concise summary of your findings, structured in bullet points or short paragraphs. Focus on actionable insights relevant to investors or market analysts."

    jrequest = {
        "company_id": str(db_company.id),
        "prompt": prompt + content,
        "article": content,
        "system": system,
    }

    db_prompt = DB_CompanyPrompt(**jrequest)
    db_prompt.save()

    data = {
        'type': 'company_prompt',
        'system': system,
        'prompt': prompt,
        'company': db_company.safe_name,
        'prefix': "9_" + db_company.safe_name,
        'id': str(db_prompt.id),
        'callback_url': "https://tothemoon.life/api/company/ai_prompt"
    }

    if os.environ.get('FLASK_ENV', None) == "development":
        data['callback_url'] = "http://dev.tothemoon.life/api/company/ai_prompt"

    response = requests.post("https://lachati.com/api_v1/upload-json", json=data)
    response.raise_for_status()

    try:
        json_response = response.json()
        print_json(json_response)

        db_prompt.update(**{'ai_upload_date': datetime.now(), 'ai_queue_size': json_response['queue_size']})
    except Exception as e:
        print_exception(e, "CRASH READING RESPONSE")

    return db_prompt


@blueprint.route('/prompt/<string:ticker>', methods=['GET', 'POST'])
def api_get_company_prompt(ticker):
    """ Example of creating a prompt:
        https://dev.tothemoon.life/api/company/prompt/NASDAQ:INTC
    """
    db_company = DB_Company.objects(exchange_tickers=ticker).first()
    if not db_company:
        return get_response_error_formatted(404, {'error_msg': "Business doesn't have tickers!"})

    processed = api_build_company_state_query(db_company)
    return get_response_formatted({'processed': processed})


@blueprint.route('/ai_prompt', methods=['GET', 'POST'])
#@api_key_or_login_required
#@admin_login_required
def api_prompt_callback_company():
    json = request.json

    if 'id' not in json:
        return get_response_error_formatted(400, {'error_msg': "An id is required"})

    db_prompt = DB_CompanyPrompt.objects(id=json['id']).first()

    if not db_prompt:
        print_r(" FAILED UPDATING AI " + json['id'])
        return get_response_formatted({})

    update = {}
    update['last_visited_date'] = datetime.now()
    update['last_visited_verbose'] = datetime.now().strftime("%Y/%m/%d, %H:%M:%S")
    update['status'] = "PROCESSED"
    update['ai_summary'] = json['result']

    db_prompt.update(**update)

    return get_response_formatted({})


@blueprint.route('/query_prompts', methods=['GET', 'POST'])
#@api_key_or_login_required
def api_company_get_query_prompts():
    delete = request.args.get("cleanup", None)

    prompts = build_query_from_request(DB_CompanyPrompt, global_api=True)
    ret = {'prompts': prompts}

    if delete:
        prompts.delete()

    return get_response_formatted(ret)

import io
import re
import socket
from datetime import datetime

import qrcode
import requests
from api import (api_key_or_login_required, cache,
                 get_response_error_formatted, get_response_formatted)
from api.company import blueprint
from api.company.models import DB_Company, DB_CompanyPrompt
from api.config import get_api_AI_service, get_api_entry
from api.file_cache import api_file_cache
from api.print_helper import *
from api.query_helper import (build_query_from_request, get_timestamp_verbose,
                              is_mongo_id)
from api.ticker.tickers_helpers import ticker_exchanges_cleanup_dups
from flask import request, send_file
from mongoengine.queryset.visitor import Q


@blueprint.route('/query', methods=['GET', 'POST'])
@api_file_cache(expiration_secs=120)
def api_company_get_query():
    """
    Example of queries: https://dev.gputop.com/api/company/query?founded=1994

    https://gputop.com/api/company/query?exchange_tickers=NASDAQ:INTC
    """

    companies = build_query_from_request(DB_Company, global_api=True)

    if len(companies) == 0:
        # Patch to fix issue with tickers that refer to the same company.
        query = request.args.get("exchange_tickers", None)
        if query:
            query = query.upper()

        if '-' in query:
            arr = query.split('-')
            companies = DB_Company.objects(exchange_tickers=arr[0])

    res = []
    for company in companies:
        api_create_ai_regex_tool(company)
        res.append(company.serialize())

    ret = {'companies': res}
    return get_response_formatted(ret)


@blueprint.route('/query_cache', methods=['GET', 'POST'])
@api_file_cache(expiration_secs=86400)
def api_company_get_query_long():
    """ Long cache query """
    return api_company_get_query()


def company_get_suggestions(text, only_tickers=False):
    """ """
    from api.ticker.tickers_helpers import standardize_ticker_format

    company = None
    words = text.strip().split(" ")
    if len(words) == 1:  # Possible ticker the user is looking for
        ticker = words[0]
        pattern = r"^[A-Za-z0-9]+[.:]?[A-Za-z0-9]*$"

        if re.match(pattern, ticker):
            full_symbol = standardize_ticker_format(ticker)
            query = Q(exchange_tickers=full_symbol)
            company = DB_Company.objects(query).first()
            if not company:
                from api.ticker.batch.yfinance.ytickers_pipeline import \
                    yticker_check_tickers
                from api.ticker.connector_yfinance import fetch_tickers_info

                print_r("! Someone wants to index this company " + full_symbol)
                info = fetch_tickers_info(ticker)
                if info:
                    yticker_check_tickers([ticker])

            else:
                if only_tickers:
                    return [full_symbol]

                return [company]

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
@api_file_cache(expiration_secs=86400)
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
@api_key_or_login_required
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
@api_file_cache(expiration_secs=600)
def api_get_business_info(biz_name):
    """ Business get info
    ---
    """
    print(" LOAD " + biz_name)
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


@blueprint.route('/query_symbol/<symbol>', methods=['GET', 'POST'])
@api_file_cache(expiration_secs=300)
def api_prompt_get_query_symbol(symbol):
    """

    """

    db_company = DB_Company.objects(exchange_tickers=symbol).first()
    if not db_company:
        return get_response_formatted({'empty': 1, 'news': []})

    extra_args = {'company_id': str(db_company.id)}

    ret = api_company_build_prompts_query(extra_args=extra_args)

    ret['companies'] = {str(db_company.id): db_company.serialize()}
    return get_response_formatted(ret)


@blueprint.route('/categories', methods=['GET', 'POST'])
@api_file_cache(expiration_secs=86400)
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
    api_create_ai_regex_tool(company)

    prompt = "Summarize this, and format it max one paragraph and 5 bullet points, use markdown to highlight important facts: "

    if not company['long_business_summary']:
        return

    if not force_summary and 'ai_summary' in company:
        return

    if company.ai_upload_date:
        age_update = (datetime.now() - company.ai_upload_date).total_seconds() / 60
        if age_update < 600:
            return

    data = {
        'type': 'summary',
        'id': str(company['id']),
        'message': prompt + company['long_business_summary'],
        'prefix': "COMPANY_" + str(company['safe_name']),
        'callback_url': get_api_entry() + "/company/ai_callback",
        'hostname': socket.gethostname(),
        'tickers': str(company['exchange_tickers']),
    }

    print_b(" INDEX " + company['safe_name'])
    response = requests.post(get_api_AI_service(), json=data)
    response.raise_for_status()

    company.update(**{'ai_upload_date': datetime.now()})


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
    try:
        json = request.json
    except:
        print_r(" MISSING JSON ")
        return get_response_formatted({})

    business = DB_Company.objects(id=json['id']).first()

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


def api_create_ai_regex_tool(company, invalidate=False):
    from api.news.models import DB_News

    if not invalidate and company['regex']:
        return

    if not company['long_business_summary']:
        return

    description = "Given the company name |" + company['company_name'] + "|"

    if 'long_name' in company and company['long_name'] and company['long_name'] != company['company_name']:
        description += " or |" + company['long_name'] + "| "

    description += "Create a regular expression that can find this company "
    description += "in any text so we can replace it with a link to the company. "
    description += "Make sure it defines the company and only the company in any part of the text."

    system = "You are an python expert developer in regular expressions and backend, you are writing scripts to parse website articles to match articles with companies."
    create_regex = {
        "type": "function",
        "function": {
            "name": "regular_expression",
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {
                    "regex": {
                        "type": "string",
                        "description": "Regex for python for " + company['company_name'],
                    },
                    "regex_explanation": {
                        "type": "string",
                        "description": "Chain of though on how this regex works.",
                    },
                },
                "required": ["regex"],
            },
        },
    }

    article_content = ""
    user_prompt = "Examples of articles that might contain the company name: "
    db_news = DB_News.objects(ai_summary__exists=1,
                              related_exchange_tickers__size=1,
                              related_exchange_tickers=company.exchange_tickers[0]).order_by('-creation_date').limit(5)
    for article in db_news:
        article_content += article['ai_summary']

    print(article_content)

    arr_messages = [{
        "role": "assistant",
        "content": str(company.long_name) + " " + str(company.long_business_summary),
    }, {
        "role": "system",
        "content": system,
    }, {
        "role": "user",
        "content": user_prompt + article_content[:4096],
    }]

    data = {
        'type': 'raw_llama',
        'subtype': 'company_regex',
        'id': str(company.id),
        'model': "llama3.3",
        'raw_messages': arr_messages,
        'raw_tools': [create_regex],
        'callback_url': get_api_entry() + "/company/ai_callback_prompt",
        'hostname': socket.gethostname(),
    }

    if invalidate:
        data['prefix'] = "0_REGEX_"
    else:
        data['prefix'] = "REGEX_"

    try:
        response = requests.post(get_api_AI_service(), json=data)
        response.raise_for_status()

        json_response = response.json()
        return json_response

    except Exception as e:
        print_exception(e, "CRASH READING RESPONSE")

    return "FAILED"


@blueprint.route('/ai_callback_prompt', methods=['GET', 'POST'])
#@api_key_or_login_required
def api_company_callback_ai_callback_prompt():
    """ """
    #print("Raw data:", request.data.decode('utf-8'))
    #print("Headers:", request.headers)

    json = request.json

    business = DB_Company.objects(id=json['id']).first()

    if 'type' in json:
        print_b(" AI_CALLBACK " + json['id'])

        t = json['type']
        if t == 'dict':
            functions = {'tools': json['dict']}

            try:
                if json['subtype'] == "company_regex":
                    regex = json['dict'][0]["function"]["arguments"]["regex"]
                    compiled_pattern = re.compile(regex)

                    business.update(**{'regex': regex})
            except Exception as e:
                print_exception(e, "CRASHED")

    ret = {}
    return get_response_formatted(ret)


@blueprint.route('/get_related/<string:full_ticker>', methods=['GET', 'POST'])
@api_file_cache(expiration_secs=86400)
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

    db_company = DB_Company.objects(id=company_id).first()
    if not db_company or not db_company.exchange_tickers:
        return get_response_error_formatted(404, {'error_msg': "Business doesn't have tickers!"})

    ticker = db_company.exchange_tickers[-1]
    result = api_create_ai_regex_tool(db_company, invalidate=True)

    query_report = api_build_company_state_query(db_company, forced=True)

    processed = ticker_process_invalidate_full_symbol(ticker)

    return get_response_formatted({'processed': processed, 'result': result, 'query_report': query_report})


@blueprint.route('/analysis/batch', methods=['GET', 'POST'])
def api_update_company_summary():
    """ Create a summary for the current company.
    """

    from api.ai.routes import get_api_AI_availability

    my_count = get_api_AI_availability("process")
    if my_count == -1 or my_count > 10:
        return get_response_formatted({'my_count': my_count})

    companies = DB_Company.objects(last_analysis_date__exists=0, long_name__exists=1).limit(10)
    if len(companies) == 0:
        companies = DB_Company.objects(last_analysis_date__exists=1,
                                       long_name__exists=1).order_by("+last_analysis_date").limit(10)

    reports = []
    for db_company in companies:

        db_company.update(**{'last_analysis_date': datetime.now()})

        ret = api_build_company_state_query(db_company)
        if ret == -1 or ret == True or not ret:
            continue

        try:
            if 'last_analysis_date' in db_company and db_company['last_analysis_date']:
                ret['last_analysis_date_verbose'] = db_company['last_analysis_date'].strftime("%Y/%m/%d, %H:%M:%S")
                print(" DATE " + ret['last_analysis_date_verbose'])
        except Exception as e:
            print_exception(e, "CRASHED")

        reports.append(ret)

    return get_response_formatted({'query_report': reports})


def api_build_company_state_query(db_company, forced=False):
    from datetime import timedelta

    from api.ai.routes import get_api_AI_availability
    from api.prompts.routes import api_create_content_from_tickers

    if not db_company:
        return None

    if not db_company.long_name:
        print_r(" MISSING COMPANY NAME ")
        return True

    from api.news.routes import get_portfolio_query

    if not forced:
        my_count = get_api_AI_availability("process")
        if my_count == -1 or my_count > 10:
            return -1

        cache_review_date = datetime.now() - timedelta(days=1)
        db_prompt = DB_CompanyPrompt.objects(company_id=str(db_company.id),
                                             ai_upload_date__gte=cache_review_date).first()
        if db_prompt:
            return db_prompt

    content = ""
    news, tkrs = get_portfolio_query(tickers_list=db_company.exchange_tickers)

    company_finances = api_create_content_from_tickers(db_company.exchange_tickers, add_days="8,31,365")

    if not news:
        return None

    if len(news) == 0:
        # No news to process
        return None

    unique_tickers = set()

    for index, article in enumerate(news):
        try:
            unique_tickers = set(article.related_exchange_tickers) | unique_tickers
            content += "| Article " + str(index) + " from " + str(article.publisher) + "\n"
            content += "| Title: " + str(article.get_title()) + "\n"
            content += str(article.get_summary()) + "\n"
            content += "\n---\n"
        except Exception as e:
            print_exception(e, "CRASHED READING ARTICLE")

    #tickers = str.join(",", unique_tickers)
    #content += "## Tickers: " + tickers + "\n\n"

    content += company_finances

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
    system += "Add Unicode icons to emphasise different aspects and important information."

    prompt = "Given the articles and information for "
    prompt += db_company.long_name
    prompt += ". What is the current state of the company ?"

    jrequest = {
        "company_id": str(db_company.id),
        "prompt": prompt,
        "assistant": content,
        "system": system,
        "tickers": db_company.exchange_tickers,
    }

    db_prompt = DB_CompanyPrompt(**jrequest)
    db_prompt.save()

    assistant = "Current date " + str(datetime.now())[:16] + "."
    assistant += "Relevant articles for " + db_company.long_name + ". "

    if db_company.long_business_summary:
        assistant += str(db_company.long_business_summary) + "."

    assistant += content

    arr_messages = [{
        "role": "assistant",
        "content": assistant,
    }, {
        "role": "system",
        "content": system,
    }, {
        "role": "user",
        "content": prompt,
    }]

    data = {
        'type': 'raw_llama',
        'subtype': 'company_state',
        'company': str(db_company.safe_name),
        'raw_messages': arr_messages,
        'raw_tools': None,
        'prefix': "Z_COMPANY_SUMMARY_" + str(db_company.safe_name),
        'id': str(db_prompt.id),
        'model': "llama3.3",
        'callback_url': get_api_entry() + "/company/ai_prompt",
        'hostname': socket.gethostname(),
    }

    try:
        response = requests.post(get_api_AI_service(), json=data)
        response.raise_for_status()

        json_response = response.json()
        #print_json(json_response)

        db_prompt.update(**{'ai_upload_date': datetime.now(), 'ai_queue_size': json_response['queue_size']})
        db_prompt.reload()
    except Exception as e:
        print_exception(e, "CRASH READING RESPONSE")

    return db_prompt


@blueprint.route('/prompt/<string:ticker>', methods=['GET', 'POST'])
def api_get_company_prompt(ticker):
    """ Example of creating a prompt:
        https://domain/api/company/prompt/NASDAQ:INTC
    """
    db_company = DB_Company.objects(exchange_tickers=ticker).first()
    if not db_company:
        return get_response_error_formatted(404, {'error_msg': "Business doesn't have tickers!"})

    processed = api_build_company_state_query(db_company, forced=True)
    return get_response_formatted({'processed': processed})


@blueprint.route('/ai_prompt', methods=['GET', 'POST'])
#@api_key_or_login_required
#@admin_login_required
def api_prompt_callback_company():
    try:
        json = request.json
    except:
        print_r(" WTF ")
        return get_response_formatted({})

    if 'id' not in json:
        return get_response_error_formatted(400, {'error_msg': "An id is required"})

    db_prompt = DB_CompanyPrompt.objects(id=json['id']).first()

    if not db_prompt:
        print_r("COMPANY FAILED UPDATING AI " + json['id'])
        return get_response_formatted({})

    update = {}
    update['last_visited_date'] = datetime.now()
    update['last_visited_verbose'] = datetime.now().strftime("%Y/%m/%d, %H:%M:%S")
    update['status'] = "PROCESSED"
    update['ai_summary'] = json['result']

    db_prompt.update(**update)

    return get_response_formatted({})


def api_company_build_prompts_query(extra_args=None):
    extra = extra_args.get("extra", "")

    prompts = build_query_from_request(DB_CompanyPrompt, global_api=True, extra_args=extra_args)
    ret = {'news': prompts}

    if 'include_company' not in extra:
        return ret

    companies = {}
    reasonable_fields = ['company_name', 'website', 'exchange_tickers']
    for prompt in prompts:
        if prompt['company_id'] in companies:
            continue

        c = DB_Company.objects(id=prompt['company_id']).only(*reasonable_fields).first()
        companies[prompt['company_id']] = c

    ret['companies'] = companies
    return ret


@blueprint.route('/query_prompts', methods=['GET', 'POST'])
#@api_key_or_login_required
@api_file_cache(expiration_secs=3600)
def api_company_get_query_prompts():
    delete = request.args.get("cleanup", None)

    ret = api_company_build_prompts_query(request.args)
    if delete and current_user.is_admin:
        prompts.delete()

    return get_response_formatted(ret)


@blueprint.route('/latest_prompts', methods=['GET', 'POST'])
#@api_key_or_login_required
@api_file_cache(expiration_secs=300, ignore_dev=True)
def api_company_get_query_prompts_latest():
    """
    Abstraction so we don't call this very long query:
    /api/company/query_prompts?order_by=-ai_upload_date&only=&ai_summary__exists=1&extra=include_company
    """
    new_args = {
        'order_by': "-ai_upload_date",
        'only': "company_id,ai_summary,ai_upload_date",
        'ai_summary__exists': "1",
        'extra': "include_company",
    }

    new_args.update(request.args)
    ret = api_company_build_prompts_query(new_args)

    return get_response_formatted(ret)


@blueprint.route('/financials/get/<string:ticker_id>', methods=['GET', 'POST'])
@api_file_cache(expiration_secs=300)
def api_get_ticker_financials(ticker_id):
    """
        Returns a list of tickers that the user is watching.
    """
    from api.ticker.batch.yfinance.ytickers_pipeline import \
        ticker_update_financials
    from api.ticker.routes import ticker_get_history_date_days

    db_company = DB_Company.objects(exchange_tickers=ticker_id).first()
    forced = request.args.get("forced", None)

    fin = {}
    if not db_company or 'exchange_tickers' not in db_company:
        return get_response_formatted(fin)

    exchange_tickers = ticker_exchanges_cleanup_dups(db_company['exchange_tickers'])

    for full_symbol in exchange_tickers:
        try:
            ticker_data = ticker_update_financials(full_symbol, force=forced)
            if not ticker_data:
                continue

            # TODO: We might have this info already cached on ticker_data since now we generate it on the fly.
            # With a timeout of 24h
            add_days = request.args.get("add", None)
            if add_days:
                list_days = add_days.split(',')
                for test in list_days:
                    res = ticker_get_history_date_days(full_symbol, int(test))

                    try:
                        change = ((ticker_data['day_high'] - res['close']) / res['close']) * 100
                        res['change_pct'] = change
                        ticker_data['days_' + test] = res
                    except:
                        pass

            fin[full_symbol] = ticker_data

        except Exception as e:
            print_exception(e, "CRASHED FINANCIAL UPDATES")

    ret = {'exchange_tickers': exchange_tickers, 'financials': fin}
    return get_response_formatted(ret)


@blueprint.route('/cleanup', methods=['GET', 'POST'])
def api_get_nms_cleanup():
    """
        Looks for companies that have only NMS tickers and tries to merge them with the real ones.

        NYS is the exchange code for the primary instrument code trading in the
        New York Stock Exchange (NYSE) and NYQ is the exchange
        code for the consolidated instrument code when it is primarily trading in NYSE.

        The National Market System (NMS) is a regulatory mechanism that
        governs the operations of securities trading in the United States.
    """
    cleanup_tickers_id = request.args.get("cleanup_tickers_id", None)
    if cleanup_tickers_id:
        res = []
        company = DB_Company.objects(id=cleanup_tickers_id).first()
        exchange_tickers = [company['exchange_tickers'][0]]
        exchanges = [company['exchanges'][0]]
        company.update(**{'exchange_tickers': exchange_tickers, 'exchanges': exchanges})
        res.append(company)
        print(">> COMPANY " + str(company.safe_name))

        return get_response_formatted({'res': res})

    legacy_fix = request.args.get("legacy_fix", None)
    if legacy_fix:
        res = []
        legacy = DB_Company.objects(ia_summary__exists=1, ai_summary__exists=0)
        for company in legacy:
            company.update(**{'ai_summary': company['ia_summary'], 'ia_summary': None})
            res.append(company)
            print(">> COMPANY " + str(company.safe_name))

        return get_response_formatted({'res': res})

    generics = request.args.get("generics", None)
    if generics:

        GENERICS = ["NMS:", "NYQ:"]

        for test in GENERICS:
            dups = DB_Company.objects(exchange_tickers__istartswith=test)

            for co in dups:
                exchange, ticker = co.exchange_tickers[0].split(":")
                candidate_list = DB_Company.objects(exchange_tickers__iendswith=":" + ticker, id__ne=co.id)

                c = len(candidate_list)
                if c == 0:
                    continue

                if c == 1:
                    candidate = candidate_list.first()
                    print_b(co.long_name + " " + str(co.exchange_tickers) + " MERGE " + str(candidate.exchange_tickers))

                    #candidate.exchange_tickers.append(exchange + ":" + ticker)
                    #candidate.update(**{'exchange_tickers': candidate.exchange_tickers})

                    candidate.delete()
                    co.delete()
                else:
                    print_r(co.long_name + " NEEDS RESOLVE ")
                    for c in candidate_list:
                        print_b(c.long_name + " MERGE " + str(c) + " " + str(c.exchange_tickers))

        return get_response_formatted({'dups': dups})

    return get_response_formatted({})


@blueprint.route('/sitemap.xml', methods=['GET', 'POST'])
@api_file_cache(expiration_secs=86400, data_type="xml")
def api_sitemap_analysis():
    import urllib.parse

    from flask import Response

    companies = DB_Company.objects()

    xml_content = """<?xml version='1.0' encoding='UTF-8'?><urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"""

    for company in companies:
        symbol = company.get_primary_ticker()

        if not company.company_name:
            company_name = ""
        else:
            company_name = urllib.parse.quote_plus(company.company_name)
        xml_content += f"<url><loc>https://headingtomars.com/analysis/{ symbol }#{ company_name }</loc></url>"

    xml_content += "</urlset>"

    return Response(xml_content, mimetype='text/xml')


@blueprint.route('/sitemap_tickers.xml', methods=['GET', 'POST'])
@api_file_cache(expiration_secs=86400, data_type="xml")
def api_sitemap_tickers():
    import urllib.parse

    from flask import Response

    companies = DB_Company.objects()

    xml_content = """<?xml version='1.0' encoding='UTF-8'?><urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"""

    for company in companies:
        symbol = company.get_primary_ticker()

        if not company.company_name:
            company_name = symbol
        else:
            company_name = urllib.parse.quote_plus(company.company_name + " " + symbol)

        for et in company.exchange_tickers:
            xml_content += f"<url><loc>https://headingtomars.com/ticker/{ et }#{ company_name }</loc><changefreq>weekly</changefreq></url>"

    xml_content += "</urlset>"

    return Response(xml_content, mimetype='text/xml')


@blueprint.route('/cleanup_dups', methods=['GET', 'POST'])
def api_company_aggregate_dups():
    """
        Group by long_name and find duplicates to merge
    """
    from api.query_helper import mongo_to_dict_helper
    from api.ticker.models import DB_Ticker

    pipeline = [
        {
            "$group": {
                "_id": "$long_name",
                "ids": {
                    "$push": "$_id"
                },
                "count": {
                    "$sum": 1
                }
            }
        },
        {
            "$match": {
                "count": {
                    "$gt": 1
                }
            }
        }  # Filter groups with more than one document
    ]

    ret = {}

    ret['result'] = mongo_to_dict_helper(DB_Company.objects.aggregate(*pipeline))
    ret['pipeline'] = [pipeline]

    merge_companies = request.args.get("cleanup", None)
    if not merge_companies:
        return get_response_formatted(ret)

    try:
        for res in ret['result']:
            if not isinstance(res['_id'], str) or res['_id'] == "":
                print_r(" CHECK THIS " + str(res['_id']))
                continue

            print_r(" MERGING " + res['_id'])

            first = None

            del_keys = ['id', 'validate', 'exchanges', 'exchange_tickers']

            for i in res['ids']:
                db_company = DB_Company.objects(id=i).first()
                if not first:
                    first = db_company
                    exchanges = mongo_to_dict_helper(db_company.exchanges)
                    exchange_tickers = mongo_to_dict_helper(db_company.exchange_tickers)
                    continue

                my_update = mongo_to_dict_helper(db_company)

                exchanges.extend(my_update['exchanges'])
                exchange_tickers.extend(my_update['exchange_tickers'])

                for key in del_keys:
                    if key in my_update:
                        del my_update[key]

                for k, v in my_update.items():
                    if not v:
                        continue

                    first[k] = v

                first.save(validate=False)
                db_company.delete()

            exchanges = list(set(exchanges))
            exchange_tickers = list(set(exchange_tickers))

            first.update(**{'exchanges': exchanges, 'exchange_tickers': exchange_tickers})

            new_id = str(first.id)
            for i in res['ids']:
                if i == str(first.id):
                    continue

                db_ticker = DB_Ticker.objects(company_id=i).first()
                if not db_ticker:
                    print_r(" TICKER NOT FOUND " + i)
                    continue

                print_b(" REPLACE " + str(db_ticker.company_id) + " >> " + new_id)

                #db_ticker.update(** { 'company_id': new_id })

    except Exception as e:
        print_exception(e, "CRASHED MERGING")

    return get_response_formatted(ret)


@blueprint.route('/index/chromadb', methods=['GET', 'POST'])
#@api_key_or_login_required
#@admin_login_required
def api_company_reindex_in_chromadb():
    """
        We call this function to index articles that we haven't added to our chroma search
    """
    from .chromadb import (chromadb_company_index_document,
                           chromadb_delete_all_company)

    if request.args.get("reset", None):
        updated_count = DB_Company.objects(ai_summary__exists=1, is_chromadb=True).update(set__is_chromadb=False)
        chromadb_delete_all_company()
        return get_response_formatted({'count': updated_count})

    companies = DB_Company.objects(ai_summary__exists=1, is_chromadb__ne=True).order_by('-creation_date').limit(10000)

    ret = []
    count = 0
    for item in companies:
        print_b(f"{count} CHROMA INDEX {str(item.id)} ")
        count += 1
        ret.append(chromadb_company_index_document(item))
        item.update(**{'is_chromadb': True})

    ret = {'chroma': ret}
    return get_response_formatted(ret)


@blueprint.route('/vector_search/<string:search_terms>', methods=['GET', 'POST'])
def api_vector_search_company(search_terms):
    from .chromadb import chromadb_company_search

    ret = chromadb_company_search(search_terms)
    return get_response_formatted({'result': ret})


@blueprint.route('/article/<string:news_id>', methods=['GET', 'POST'])
def api_vector_classify_article(news_id):
    from api.news.models import DB_News

    from .chromadb import (chromadb_company_search,
                           extract_companies_and_tickers)

    article = DB_News.objects(id=news_id).first()

    if not article:
        return get_response_formatted({'msg': "no article found"})

    doc = str(article.source_title) + " "
    doc += article.get_summary() + " "
    doc += str(article.ai_summary) + " "
    doc += article.get_raw_article()

    ret = chromadb_company_search(doc)

    companies, tickers = extract_companies_and_tickers(doc)

    spa = {'companies': companies, 'tickers': tickers}

    validated = []
    unvalid = []
    for company in companies:
        query = Q()
        for term in company.split():
            query &= Q(company_name__regex=r'\b' + term + r'\b', company_name__icontains=term)

        results = DB_Company.objects(query)
        for c in results:
            match = None

            try:
                match = re.match(c.regex, company)
                if match:
                    print(f"Valid: {c.company_name}")
                    validated.append([c.company_name, company, c.regex])
            except:
                pass

            if not match:
                unvalid.append([c.company_name, company, c.regex])

    spa['validated'] = validated
    spa['unvalid'] = unvalid

    #db.collection.find(
    #    { $text: { $search: "word" } },
    #    { score: { $meta: "textScore" } }
    #).sort({ score: { $meta: "textScore" } })

    update = {'NER': validated}

    if unvalid:
        update['NER_unvalid'] = unvalid

    article.update(**update)

    return get_response_formatted({'article': doc[:256], 'spacy': spa, 'result': ret})

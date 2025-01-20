import os
import socket
from datetime import datetime

import requests
from api import (admin_login_required, api_key_or_login_required,
                 get_response_error_formatted, get_response_formatted)
from api.company.models import DB_Company
from api.config import (get_api_AI_default_service, get_api_AI_service,
                        get_api_entry, is_api_development)
from api.news.models import DB_News
from api.news.routes import get_portfolio_query
from api.print_helper import *
from api.prompts import blueprint
from api.prompts.models import DB_UserPrompt
from api.query_helper import build_query_from_request
from api.ticker.routes import ticker_get_history_date_days
from api.ticker.tickers_helpers import ticker_exchanges_cleanup_dups
from api.tools.markdownify import markdownify
from flask import request
from flask_login import current_user


def api_save_user_prompt(jrequest):
    print_g("Save user prompt")

    old_prompts = DB_UserPrompt.objects(username=current_user.username, subtype="EMAIL_SUMMARY",
                                        status="active").update(status='inactive')

    db_prompt = DB_UserPrompt(**jrequest)
    db_prompt.status = "active"
    db_prompt.save()


@blueprint.route('/create', methods=['GET', 'POST'])
@api_key_or_login_required
def api_create_prompt_local():
    """ Create a new prompt to be resolved """

    print("======= CREATE A SINGLE PROMPT =============")

    jrequest = request.json

    if 'id' in jrequest:
        return get_response_error_formatted(400, {'error_msg': "Error, please use UPDATE to update an entry"})

    jrequest['prompt'] = markdownify(jrequest['prompt']).strip()

    match jrequest.get('subtype', None):
        case "EMAIL_SUMMARY":
            api_save_user_prompt(jrequest)

    if 'system' in jrequest and jrequest['system']:
        jrequest['system'] = markdownify(jrequest['system']).strip()

    jrequest['status'] = "INDEX"

    db_prompt = DB_UserPrompt(**jrequest)
    db_prompt.save()

    priority = False
    try:
        if current_user.subscription.status == "active":
            priority = True

    except Exception as e:
        pass

    res = api_create_prompt_ai_summary(db_prompt, priority)
    res2 = api_let_AI_search_for_information(db_prompt, priority)
    ret = {"prompts": [db_prompt]}

    if 'queue_size' in res:
        ret['queue_size'] = res['queue_size']

    return get_response_formatted(ret)


@blueprint.route('/query', methods=['GET', 'POST'])
@api_key_or_login_required
def api_prompt_get_query():
    prompts = build_query_from_request(
        DB_UserPrompt, global_api=False, append_public=False, extra_args=None)
    return get_response_formatted({'prompts': prompts})


@blueprint.route('/latest_system', methods=['GET', 'POST'])
@api_key_or_login_required
def api_prompt_get_system_query():
    extra_args = {'username__exists': 1, 'username': current_user.username,
                  'order_by': '-creation_date', 'limit': 1}

    prompts = build_query_from_request(
        DB_UserPrompt, global_api=False, append_public=False, extra_args=extra_args)
    return get_response_formatted({'prompts': prompts})


@blueprint.route('/get/<string:prompt_id>', methods=['GET', 'POST'])
def api_get_prompt_helper(prompt_id):
    """ Prompt ID
    ---
    """
    prompts = DB_UserPrompt.objects(id=prompt_id).first()

    if not prompts:
        return get_response_error_formatted(404, {'error_msg': "User prompt not found"})

    ret = {'prompts': [prompts]}
    return get_response_formatted(ret)


@blueprint.route('/rm/<string:prompt_id>', methods=['GET', 'POST'])
@blueprint.route('/remove/<string:prompt_id>', methods=['GET', 'POST'])
@api_key_or_login_required
def api_remove_a_prompt_by_id(prompt_id):
    """ Prompt deletion
    ---
    """

    prompt_type = request.args.get("type", None)

    # CHECK API ONLY ADMIN
    if prompt_id == "ALL":
        if not prompt_type:
            res = DB_UserPrompt.objects(username=current_user.username)
        else:
            res = DB_UserPrompt.objects(
                username=current_user.username, type=prompt_type)

        ret = {'status': "deleted", 'prompts': res}
        res.delete()
        return get_response_formatted(ret)

    prompts = DB_UserPrompt.objects(
        id=prompt_id, username=current_user.username).first()

    if not prompts:
        return get_response_error_formatted(404, {'error_msg': "The prompt was not found for the current user"})

    ret = {'status': "deleted", 'prompts': prompts}

    prompts.delete()
    return get_response_formatted(ret)


@blueprint.route('/rm', methods=['GET', 'POST'])
def api_remove_a_prompt_by_id_request():
    prompt_id = request.args.get("id", None)
    return api_remove_a_prompt_by_id(prompt_id)


@blueprint.route('/ai_callback', methods=['GET', 'POST'])
# @api_key_or_login_required
# @admin_login_required
def api_prompt_callback_ai_summary():
    json = request.json

    if 'id' not in json:
        return get_response_error_formatted(400, {'error_msg': "An id is required"})

    db_prompt = DB_UserPrompt.objects(id=json['id']).first()

    if not db_prompt:
        print_r("PROMPT FAILED UPDATING AI " + json['id'])
        return get_response_formatted({})

    if 'type' in json:
        print_b(" NEWS AI_CALLBACK " +
                json['id'] + " " + str(db_prompt.prompt))

        update = {}

        t = json['type']
        if t == 'dict':
            tools = json['dict']
            ai_summary = json['ai_summary']
            update = {'ai_summary': ai_summary, 'tools': tools}

        if t == 'user_prompt':
            update = {'ai_summary': json['result']}

        update['last_visited_date'] = datetime.now()
        update['last_visited_verbose'] = datetime.now().strftime(
            "%Y/%m/%d, %H:%M:%S")

        if is_api_development():
            update['dev'] = True

        update['status'] = "PROCESSED"

        if 'raw' in json:
            update['raw'] = json['raw']

        if 'raw_tools' in json:
            update['raw_tools'] = json['raw_tools']

        db_prompt.update(**update, is_admin=True)

    ret = {}
    return get_response_formatted(ret)


@blueprint.route('/set/<string:my_id>/<string:my_key>', methods=['GET', 'POST'])
@api_key_or_login_required
@admin_login_required
def api_set_news_property_content_key(my_id, my_key):
    """ Sets this content variable """

    value = request.args.get("value", None)
    if not value and 'value' in request.json:
        value = request.json['value']

    if value == None:
        return get_response_error_formatted(400, {'error_msg': "Wrong parameters."})

    news = DB_News.objects(id=my_id).first()

    if not news:
        return get_response_error_formatted(400, {'error_msg': "Wrong parameters."})

    if not news.set_key_value(my_key, value):
        return get_response_error_formatted(400, {'error_msg': "Something went wrong saving this key."})

    ret = {'news': [news]}
    return get_response_formatted(ret)


def api_build_chats_query(db_prompt):
    content = ""
    if 'CHAT' in db_prompt.selection:
        db_prompts = DB_UserPrompt.objects(username=current_user.username, ai_summary__ne=None,
                                           selection="CHAT").order_by('+creation_date').limit(25)
        content += "---"
        for db_prompt in db_prompts:
            content += "DATE> " + str(db_prompt.creation_date)[:16] + "\n\n"
            content += current_user.username + "> " + db_prompt.prompt + "\n\n"
            content += "AI> " + db_prompt.ai_summary + "\n\n"

    return content


def api_create_content_from_tickers(tickers, add_days="8,31,365"):
    from api.ticker.batch.yfinance.ytickers_pipeline import \
        ticker_update_financials

    if not tickers:
        return ""

    content = ""

    if isinstance(tickers, str):
        tickers = tickers.split(',')

    for full_symbol in tickers:
        list_days = add_days.split(',')

        try:
            data = ticker_update_financials(full_symbol, force=False)
            if not data:
                continue

            content += f"** {full_symbol} **\n"

            day_change = 0
            try:
                content += f"Price {data['price']} "
                day_change = round(
                    ((data['price'] - data['previous_close']) / data['previous_close']) * 100, 2)

                content += f"Todays change {day_change}%\n"
                content += f"PE: { data['PE'] } VOL: { int(data['volume']) } trailingEps: { data['trailingEps'] }\n"
            except:
                pass

            for test in list_days:
                res = ticker_get_history_date_days(full_symbol, int(test))
                if not res:
                    continue

                try:
                    change = round(
                        ((data['day_high'] - res['close']) / res['close']) * 100, 2)

                    content += f"Change {test} days {change}%\n"
                except:
                    pass
        except Exception as e:
            print_exception(e, "Crashed loading ticker prices")

    print(content)
    return content


def api_create_content_from_news(news, append_tickers=False):
    if not news:
        return ""

    unique_tickers = set()
    content = ""

    date = str(datetime.now().strftime("%Y/%m/%d"))
    for index, article in enumerate(news):

        try:
            if article.creation_date:
                article_date = str(article.creation_date.strftime("%Y/%m/%d"))
                print_g(article_date + " >> " + article.get_title())

                if date != article_date:
                    content += "| Date " + article_date + "\n"
                    date = article_date

            unique_tickers = set(
                article.related_exchange_tickers) | unique_tickers
            content += "| " + str(index) + " from " + article.publisher + "\n"

            if article.stock_price and len(article.related_exchange_tickers) == 1:
                content += "| Stock Price " + str(article.related_exchange_tickers[0]) + ":" + str(
                    article.stock_price) + "\n"

            content += article.get_title() + "\n"

            paragraph = article.get_paragraph()
            if paragraph:
                content += paragraph[:200] + "\n\n"

            if 'ai_summary' in article:
                content += article['ai_summary'][:2048] + "\n\n"

        except Exception as e:
            print_exception(e, "CRASHED ARTICLES ")

    if append_tickers:
        tickers = str.join(",", unique_tickers)
        content += "## Tickers: " + tickers + "\n\n"

    return content


def api_build_article_query(db_prompt):
    news = None
    tkrs = None

    extra_args = {'interest_score__gte': 7,
                  'order_by': '-creation_date', 'reversed': 1}

    if 'PORTFOLIO' in db_prompt.selection:
        news, tkrs = get_portfolio_query(my_args=extra_args)
        if not news:
            news, tkrs = get_portfolio_query(
                tickers_list=["NASDAQ:INTC", "NASDAQ:NVDA", "NASDAQ:AAPL"])
    else:
        news, tkrs = get_portfolio_query(
            tickers_list=db_prompt.selection, my_args=extra_args)

    content = api_create_content_from_news(news)
    return content


def cut_string(s, limit):
    """ Cuts from the end
        We clamp the data to some size depending on the LLM.
    """
    return s[-limit:] if len(s) > limit else s


def api_get_prompt_article(article_id):
    if not article_id:
        return ""

    article = DB_News.objects(id=article_id).first()

    news, tkrs = get_portfolio_query(
        tickers_list=article.related_exchange_tickers)

    assistant = "| We are discussing the following article with Title: "
    assistant += article.get_title()
    assistant += "| Which reads: "
    assistant += article.get_raw_article()

    # TODO Search for the latest analyst prompts to do RAG
    content = api_create_content_from_news(news)
    if content:
        assistant = content + assistant

    return content


def api_create_prompt_ai_summary(db_prompt, priority=False, force_summary=False):
    articles_content = "Portfolio state articles: " + \
        api_build_article_query(db_prompt)

    prompt = db_prompt.prompt[:4096]

    system = "Today is " + \
        str(datetime.now().strftime("%Y/%m/%d, %H:%M")) + "\n"

    if 'system' in db_prompt:
        system += db_prompt['system']
    else:
        system += "Your name is TOTHEMOON, you are an expert system that can provide financial advice due regulations in the country. \n"

    chat_content = api_build_chats_query(db_prompt)

    if 'article_id' in db_prompt:
        assistant = api_get_prompt_article(db_prompt['article_id'])
    else:
        assistant = cut_string(articles_content, 131072) + \
            cut_string(chat_content, 131072)

    data = {
        'type': 'user_prompt',
        'prompt': prompt,
        'system': system,
        'assistant': assistant,
    }

    db_prompt.update(**{
        'prompt': prompt,
        'system': system,
    })

    data['id'] = str(db_prompt.id)
    data['prefix'] = "0_PROMPT_" + db_prompt.username
    data['callback_url'] = get_api_entry() + "/prompts/ai_callback"
    data['hostname'] = socket.gethostname()

    if is_api_development():
        data['dev'] = True

    if db_prompt.use_markdown:
        data['use_markdown'] = True

    if priority:
        data['priority'] = priority

    try:
        response = requests.post(get_api_AI_service(), json=data)
        response.raise_for_status()

        json_response = response.json()
        # print_json(json_response)

        db_prompt.update(**{
            # 'raw': json_response,
            'ai_upload_date': datetime.now(),
            'ai_queue_size': json_response['queue_size']
        })

        return json_response
    except Exception as e:
        print_exception(e, "CRASH READING RESPONSE")

    return {}


@blueprint.route('/state', methods=['GET', 'POST'])
@api_key_or_login_required
@admin_login_required
def api_llama_get_state():
    response = requests.get(get_api_AI_default_service())
    response.raise_for_status()

    try:
        json_response = response.json()
        # print_json(json_response)

        return json_response
    except Exception as e:
        print_exception(e, "CRASH READING RESPONSE")

    return {}


def api_let_AI_search_for_information(db_prompt, priority=False):
    system = "You are an expert user of search and mongodb."
    system += "You are searching in several articles for an user that is asking a questions,"
    system += "you need to fill your knowledge with up to date information about the request."

    arr_messages = [{
        "role": "assistant",
        "content": "",
    }, {
        "role": "system",
        "content": system,
    }, {
        "role": "user",
        "content": db_prompt.prompt[:4096],
    }]

    search_for_information = {
        "type": "function",
        "function": {
            "name": "search_for_information",
            "description":
            "Create a list of keywords to search online or our articles in our database, including companies or financial information",
            "parameters": {
                "type": "object",
                "properties": {
                    "companies": {
                        "type": "string",
                        "description": "Comma separated list of companies to search for information.",
                    },
                    "online_query": {
                        "type": "string",
                        "description": "Search engine to get up to date information about the user request.",
                    },
                    "finance_request": {
                        "type": "string",
                        "description": "Information about a company to include up to date financials.",
                    },
                },
                "required": ["companies", "online_query"],
            },
        },
    }

    db_prompt.update(**{
        'raw_messages': arr_messages,
        'raw_tools': [search_for_information],
    })

    data = {
        'id': str(db_prompt.id),
        'type': 'raw_llama',
        'use_markdown': True,
        'raw_messages': arr_messages,
        'raw_tools': [search_for_information],
    }

    data['prefix'] = "CHAT_" + db_prompt.username
    data['callback_url'] = get_api_entry(
    ) + "/prompts/ai_callback_function_search"
    data['hostname'] = socket.gethostname()

    if is_api_development():
        data['dev'] = True

    if priority:
        data['priority'] = priority

    try:
        response = requests.post(get_api_AI_service(), json=data)
        response.raise_for_status()

        json_response = response.json()
        # print_json(json_response)

        db_prompt.update(**{
            'raw': json_response,
            'ai_upload_date': datetime.now(),
            'ai_queue_size': json_response['queue_size']
        })

        return json_response
    except Exception as e:
        print_exception(e, "CRASH READING RESPONSE")

    return {}


@blueprint.route('/ai_callback_function_search', methods=['GET', 'POST'])
# @api_key_or_login_required
# @admin_login_required
def api_prompt_ai_callback_function_call():
    json = request.json

    if 'id' not in json:
        return get_response_error_formatted(400, {'error_msg': "An id is required"})

    db_prompt = DB_UserPrompt.objects(id=json['id']).first()

    if not db_prompt:
        print_r("FUNCTION PROMPT FAILED UPDATING AI " + json['id'])
        return get_response_formatted({})

    if 'type' in json:
        print_b(" NEWS AI_CALLBACK " +
                json['id'] + " " + str(db_prompt.prompt))

        update = {}

        t = json['type']
        if t == 'dict':
            update = {'tools': json['dict']}

        update['last_visited_date'] = datetime.now()
        update['last_visited_verbose'] = datetime.now().strftime(
            "%Y/%m/%d, %H:%M:%S")

        if is_api_development():
            update['dev'] = True

        update['status'] = "PROCESSED"

        if 'raw' in json:
            update['raw'] = json['raw']

        db_prompt.update(**update, is_admin=True)

    ret = {}
    return get_response_formatted(ret)

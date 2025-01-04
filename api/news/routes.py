import copy
import re
import socket
from datetime import datetime

import requests
from api import (admin_login_required, api_key_or_login_required,
                 get_response_error_formatted, get_response_formatted)
from api.company.models import DB_Company
from api.config import get_api_AI_service, get_api_entry, is_api_development
from api.file_cache import api_file_cache
from api.news import blueprint
from api.news.models import DB_News
from api.print_helper import *
from api.query_helper import (build_query_from_request,
                              validate_and_convert_dates)
from flask import request
from flask_login import current_user


@blueprint.route('/create', methods=['GET', 'POST'])
@api_key_or_login_required
@admin_login_required
def api_create_news_local():
    """ Create a new article
    ---
    """

    print("======= CREATE A SINGLE ARTICLE =============")

    jrequest = request.json

    if 'id' in jrequest:
        return get_response_error_formatted(400, {'error_msg': "Error, please use UPDATE to update an entry"})

    if 'link' not in jrequest:
        return get_response_error_formatted(400,
                                            {'error_msg': "Missing link, not right format. Please check documentation"})

    validate_and_convert_dates(jrequest)
    article = DB_News(**jrequest)
    article.save()

    ret = {"news": [article]}
    return get_response_formatted(ret)


@blueprint.route('/search/<string:search_terms>', methods=['GET', 'POST'])
@api_file_cache(expiration_secs=86400)
def api_news_search_some_text(search_terms):
    """
    """
    if len(search_terms) < 3:
        # Not worth searching for smaller words.
        return get_response_formatted({'news': []})

    db_news = DB_News.objects(articles__icontains=search_terms + " ").order_by('-creation_date').limit(10)

    ret = {'news': db_news}
    return get_response_formatted(ret)


@blueprint.route('/query', methods=['GET', 'POST'])
@api_file_cache(expiration_secs=300)
def api_news_get_query():
    """
    Example of queries: https://dev.gputop.com/api/news/query?related_exchange_tickers=NASDAQ:NVO
    """

    extra_args = None

    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        extra_args = {"is_blocked__ne": True}

    news = build_query_from_request(DB_News, global_api=True, extra_args=extra_args)

    clean = request.args.get("cleanup", None)
    if clean and (current_user.is_admin or current_user.username in ["contact@engineer.blue", "admin"]):
        news.delete()
        ret = {'status': "deleted"}
        return get_response_formatted(ret)

    for article in news:
        article.precalculate_cache()

    ret = {'news': news}
    return get_response_formatted(ret)


@blueprint.route('/update', methods=['GET', 'POST'])
@api_key_or_login_required
@admin_login_required
def api_create_news_update_query():
    """
    Create an article or update entry
    """

    json = request.json

    ret = []
    if 'news' in json:
        for article in json['news']:
            db_article = None

            if 'id' in article:
                db_article = DB_News.objects(id=article['id']).first()

            validate_and_convert_dates(article)

            if db_article:
                db_article.update(**article)
            else:
                db_article = DB_News(**article)
                db_article.save(validate=False)

            ret.append(db_article)

    ret = {'news': ret}
    return get_response_formatted(ret)


@blueprint.route('/force_reindex/<string:news_id>', methods=['GET', 'POST'])
def api_get_force_reindex_helper(news_id):
    """ News get ID
    ---
    """
    article = DB_News.objects(id=news_id).first()

    if not article:
        return get_response_error_formatted(404, {'error_msg': "News article not found"})

    article.status = "WAITING_REINDEX"
    article.force_reindex = True
    article.save(validate=False)
    api_create_article_ai_summary(article, priority=True, force_summary=True)

    ret = {'news': [article]}
    return get_response_formatted(ret)


@blueprint.route('/get/<string:news_id>', methods=['GET', 'POST'])
@api_file_cache(expiration_secs=86400)
def api_get_news_helper(news_id):
    """ News get ID
    ---
    """
    from api.ticker.batch.workflow import ticker_reprocess_news_article

    news = DB_News.objects(id=news_id).first()

    if not news:
        return get_response_error_formatted(404, {'error_msg': "News not found"})

    extra = request.args.get("extra", None)

    if extra == "reprocess":
        ticker_reprocess_news_article(news)

    ret = {'news': [news]}

    if 'ai_summary' not in news:
        ret['no_cache'] = 1

    return get_response_formatted(ret)


@blueprint.route('/rm/<string:article_id>', methods=['GET', 'POST'])
@blueprint.route('/remove/<string:article_id>', methods=['GET', 'POST'])
@api_key_or_login_required
@admin_login_required
def api_remove_a_news_by_id(article_id):
    """ News article deletion
    ---
    """

    # CHECK API ONLY ADMIN
    if article_id == "ALL":
        DB_News.objects().delete()
        ret = {'status': "deleted"}
        return get_response_formatted(ret)

    news = DB_News.objects(id=article_id).first()

    if not news:
        return get_response_error_formatted(404, {'error_msg': "News article not found for the current user"})

    ret = {'status': "deleted", 'news': news}

    news.delete()
    return get_response_formatted(ret)


@blueprint.route('/rm', methods=['GET', 'POST'])
def api_remove_a_news_by_id_request():
    article_id = request.args.get("id", None)
    return api_remove_a_news_by_id(article_id)


def api_create_article_ai_summary(article, priority=False, force_summary=False):
    if not article['articles'] or len(article['articles']) == 0:
        return

    if not force_summary and 'ai_summary' in article:
        return

    wait_min = article.age_ai_upload_minutes()
    if not force_summary and wait_min < 120:
        print_g(article.link + " WAITING FOR AI FOR " + str(wait_min))
        return

    articles = '\n'.join(article['articles'])

    # Should we include the title to orient the AI? This seems to make it replace our generated title :(

    #if 'source_title' in article:
    #    articles = "ORIGINAL TITLE: " + article['source_title'] + "\n" + articles

    if "We, Yahoo, are part" in articles:
        print(" FAILED LOADING ARTICLE - REINDEX ")
        article.update(**{"articles": [], "force_reindex": True})
        return

    prompt = "Remove everything that is not relevant to the title: |"
    if 'source_title' in article:
        prompt += article['source_title']
    elif 'title' in article:
        prompt += article['title']

    prompt += "|. After cleanning up, summarize and format the article in max two paragraphs, "

    prompt += ". Use markdown and unicode emojis and icons to highlight important facts. "
    #prompt += "give a sentiment at the end about the company in the stock market."

    article.update(**{"ai_upload_date": datetime.now()})

    data = {
        'type': 'summary',
        'id': str(article['id']),
        'prompt': prompt,
        'article': articles[:65384],
        'callback_url': get_api_entry() + "/news/ai_callback",
        'hostname': socket.gethostname(),
    }

    if priority:
        data['priority'] = 1

    if 'link' in article:
        data['link'] = article['link']

        print(" UPLOADING TO PROCESS -> " + article['link'])

    if 'source' in article:
        data['source'] = article['source']

    try:
        response = requests.post(get_api_AI_service(), json=data)
        response.raise_for_status()

        json_response = response.json()
    except Exception as e:
        print_exception(e, "CRASH READING RESPONSE")

    article.set_state("WAITING_FOR_AI")


def api_create_news_translation(id, text, field, language):
    prompt = "You are an expert translator, translate the following into " + language + ". "

    if not text:
        return

    content = "| " + text + " |"

    data = {
        'type': 'translation',
        'id': str(id),
        'prompt': prompt,
        'field': field,
        'language': language,
        'prefix': "TRANSLATION_" + language + "_" + field + "_",
        'article': content,
        'callback_url': get_api_entry() + "/news/ai_callback_translation",
        'hostname': socket.gethostname(),
    }

    try:
        response = requests.post(get_api_AI_service(), json=data)
        response.raise_for_status()

        json_response = response.json()
    except Exception as e:
        print_exception(e, "CRASH READING RESPONSE")

    return data


@blueprint.route('/translate/<string:news_id>/<string:language>', methods=['GET', 'POST'])
def api_get_news_translate(news_id, language):
    """
        Translate into different languages use "es-ES" format
    """
    article = DB_News.objects(id=news_id).first()

    if not article:
        return get_response_error_formatted(404, {'error_msg': "News article not found"})

    #if 'title' in article:
    #    content += "<|TEXT|> " + article['title'] + "<|TEXT|> "

    data1 = api_create_news_translation(article['id'], article['ai_summary'], 'ai_summary', language)
    ret = {'news': [article], 'ai_summary': data1}

    if 'tools' in article:
        try:
            args = article['tools'][0]['function']['arguments']

            data2 = api_create_news_translation(article['id'], args['no_bullshit'], 'no_bs', language)
            ret['no_bs'] = data2

    #        content += "<|NOBS|> " + args['No_bullshit']
    #        content += "<|SUMMARY|> " + args['summary']
    #        content += "<|PARAGRAPH|> " + args['paragraph']
    #        content += "<|AI_COMMENTS|> Be you! "
        except Exception as e:
            pass

    return get_response_formatted(ret)


@blueprint.route('/ai_callback_translation', methods=['GET', 'POST'])
#@api_key_or_login_required
#@admin_login_required
def api_news_callback_ai_translation():
    """ """

    json_data = request.json

    if 'id' not in json_data:
        return get_response_error_formatted(400, {'error_msg': "An id is required"})

    article = DB_News.objects(id=json_data['id']).first()

    if not article:
        print_r("TRANSLATION FAILED UPDATING AI " + json_data['id'])
        return get_response_formatted({})

    if 'type' in json_data:
        lang = json_data['language']
        field = json_data['field']
        if 'dict' not in json_data:
            print_r("TRANSLATION 2 FAILED UPDATING AI " + json_data['id'])
            return get_response_formatted({})

        result = json_data['dict']

        if lang not in article.languages:
            article.languages.append(lang)
            article.save(validate=False)

        if 'translations' not in article:
            translations = {lang: {}}
        else:
            translations = copy.deepcopy(article['translations'])

        if lang not in translations:
            translations[lang] = {field: result}
        else:
            translations[lang][field] = result

        update = {'translations': translations}
        article.update(**update, validate=False)

    ret = {}
    return get_response_formatted(ret)


@blueprint.route('/ai_summary', methods=['GET', 'POST'])
@api_key_or_login_required
@admin_login_required
def api_news_get_news_ai_summary():
    """
        https://gputop.com/api/news/ai_summary?id=<<UIID>

    """
    index_all = request.args.get("index_all", None)

    if index_all:
        news = DB_News.objects()
    else:
        news = build_query_from_request(DB_News, global_api=True)

    for item_news in news:
        api_create_article_ai_summary(item_news, force_summary=True)

    ret = {'news': news}
    return get_response_formatted(ret)


@blueprint.route('/gif', methods=['GET', 'POST'])
#@api_key_or_login_required
def api_news_get_gif():
    """ """
    from api.gif.routes import api_gif_get_from_request
    return api_gif_get_from_request()


@blueprint.route('/ai_callback', methods=['GET', 'POST'])
#@api_key_or_login_required
#@admin_login_required
def api_news_callback_ai_summary():
    """ """

    json = request.json

    if 'id' not in json:
        return get_response_error_formatted(400, {'error_msg': "An id is required"})

    news = DB_News.objects(id=json['id']).first()

    if not news:
        print_r("NEWS FAILED UPDATING AI " + json['id'])
        return get_response_formatted({})

    if 'type' in json:
        print_b(" NEWS AI_CALLBACK " + json['id'] + " " + str(news.source_title))

        t = json['type']
        update = {}

        if 'ai_summary' in json:
            update = {'ai_summary': json['ai_summary']}

        if t == 'dict':
            tools = json['dict']

            try:
                args = {'tools': []}
                for f in tools:
                    # We flat the functions. For us they are mainly data in a DB
                    args.update(f["function"]["arguments"])
                    args['tools'].append(f["function"]["name"])

                # Sometimes llama writes the arguments wrong :(
                args = {key.lower(): value for key, value in args.items()}
                update['AI'] = args

                if 'title' in args:
                    update['title'] = args['title']

                try:
                    update['interest_score'] = int(args['interest_score'])
                except:
                    pass

                try:
                    update['sentiment_score'] = int(args['sentiment_score'])
                except:
                    pass

            except Exception as e:
                print_exception(e, "CRASHED READING SENTIMENT")

        if t == 'summary':
            if 'result' in json:
                update = {'ai_summary': json['result']}
            else:
                update = {'status': "FAILED"}
                return get_response_formatted({})

        update['last_visited_date'] = datetime.now()
        update['last_visited_verbose'] = datetime.now().strftime("%Y/%m/%d, %H:%M:%S")

        if is_api_development():
            update['dev'] = True

        update["status"] = "PROCESSED"
        try:
            news.update(**update, validate=False)
        except Exception as e:
            print_r("STOP")
            print_exception(e, "cRASHED VALIDATING")

    ret = {}
    return get_response_formatted(ret)


def get_portfolio_query(name_list="default", tickers_list=None, limit=100, my_args=None, username=None):
    from api.ticker.routes import get_watchlist_or_create

    if tickers_list:
        ls = str.join(",", tickers_list)
    else:
        watchlist = get_watchlist_or_create(name_list, username)
        ls = str.join(",", watchlist.exchange_tickers)

    extra_args = {'related_exchange_tickers__in': ls, "limit": limit}

    if my_args:
        if not 'order_by' in my_args:
            extra_args['order_by'] = '-creation_date'

        extra_args.update(my_args)

    news = build_query_from_request(DB_News, global_api=True, extra_args=extra_args)
    return news, ls


@blueprint.route('/my_portfolio', methods=['GET', 'POST'])
@api_key_or_login_required
def api_news_my_portfolio_query():
    """
    Builds a query with the current portfolio
    """
    from api.comments.routes import get_comments_count

    name = request.args.get("name", "default")

    news, portfolio_tickers = get_portfolio_query(name)

    for article in news:
        article['no_comments'] = get_comments_count(str(article.id))

    ret = {'news': news, 'portfolio': portfolio_tickers}
    return get_response_formatted(ret)


@blueprint.route('/query_test', methods=['GET', 'POST'])
def api_news_get_test_query():
    """
    """

    news = DB_News.objects(related_exchange_tickers__not__size=0).limit(10)

    ret = {'news': news}
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


@blueprint.route('/redo_database', methods=['GET', 'POST'])
@api_key_or_login_required
@admin_login_required
def api_news_redo_database_cleanup():
    news = DB_News.objects(tools__exists=1).limit(1000)

    for article in news:
        try:
            if 'gif_keywords' in article['tools']:
                AI = article['tools']
            else:
                AI = article['tools'][0]['function']['arguments']

            update = {'unset__sentiment_score': 1, 'AI': AI, 'unset__tools': 1}
            article.update(**update)
            article.reload()

        except Exception as e:
            print_exception(e, "CRASHED")
            update = {'unset__tools': 1}
            article.update(**update)

    # Remove tools if AI exists
    # DB_News.objects(AI__exists=True).update(unset__tools=1)

    for article in news:
        article['articles'] = ""

    ret = {'news': news}
    return get_response_formatted(ret)


@blueprint.route('/cleanup', methods=['GET', 'POST'])
def api_news_get_cleanup():
    """
        Looks for companies that have only NMS tickers and tries to merge them with the real ones.

        NYS is the exchange code for the primary instrument code trading in the
        New York Stock Exchange (NYSE) and NYQ is the exchange
        code for the consolidated instrument code when it is primarily trading in NYSE.

        The National Market System (NMS) is a regulatory mechanism that
        governs the operations of securities trading in the United States.
    """

    GENERICS = ["NMS:", "NYQ:"]

    for test in GENERICS:
        dups = DB_News.objects(related_exchange_tickers__istartswith=test)
        for article in dups:
            print_b(str(article.title) + " " + str(article.related_exchange_tickers))

            article.related_exchange_tickers = list(set(article.related_exchange_tickers))

            clean = []
            for et in article.related_exchange_tickers:
                if et.startswith(test):
                    exchange, ticker = et.split(":")
                    candidates = DB_Company.objects(exchange_tickers__iendswith=":" + ticker)

                    if len(candidates) == 0:
                        print_r(et + " FAILED TO FIND TICKER ")
                    elif len(candidates) > 1:
                        for c in candidates:
                            print_r("** FOUND " + str(c.exchange_tickers))

                        print_r(et + " CONFLICT RESOLUTION REQUIRED")
                        continue
                    else:
                        new_et = candidates.first().get_primary_ticker()
                        print_g(et + " REPLACE WITH => " + new_et)
                        et = new_et

                if et not in clean:
                    clean.append(et)

            print_g(str(clean))
            article.update(**{'related_exchange_tickers': clean})

    return get_response_formatted({'dups': dups})


def validate_regex_for_company(company_name: str, regex: str, text: str) -> bool:
    """
    Validates if the given regex matches only the company name in the provided text.

    Args:
        company_name (str): The expected company name (e.g., "3M Company").
        regex (str): The regex pattern to validate.
        text (str): The text to search for matches.

    Returns:
        bool: True if the regex matches only the company name, False otherwise.
    """
    try:
        # Find all matches of the regex in the text
        matches = re.findall(regex, text)

        print(str(matches))

        # Check if matches are exclusively the company name
        return matches == [company_name]
    except re.error as e:
        # Handle invalid regex patterns
        print(f"Invalid regex: {e}")
        return False


@blueprint.route('/process_regex', methods=['GET', 'POST'])
def api_regex_processing():
    """
        We ask llama to generate
    """
    extra_args = {'regex__exists': 1, 'limit': 1, 'order_by': "-last_analysis_date"}
    companies = build_query_from_request(DB_Company, global_api=True, extra_args=extra_args)

    if not companies:
        companies = DB_Company.objects(regex__exists=1).order_by('-last_analysis_date').limit(1)

    ret = []
    for company in companies:

        if not validate_regex_for_company(company.long_name, company.regex, company.ai_summary):
            print(" FAILED REGEX ")

        primary_ticker = company.get_primary_ticker()
        exchange, ticker = primary_ticker.split(":")
        db_news = DB_News.objects(related_exchange_tickers__nin=primary_ticker,
                                  ia_summary__regex=company['regex']).order_by('-creation_date').limit(10)

        ret.append(db_news)

    return get_response_formatted({'companies': companies, 'news': ret})


def api_news_group_for_sitemap(xml_content, my_group, path):
    import urllib.parse

    pipeline = []
    pipeline.append({"$group": {"_id": "$" + my_group, "count": {"$sum": 1}}})
    pipeline.append({"$sort": {"_id": 1}})
    news = DB_News.objects.aggregate(*pipeline)

    for article in news:
        if not article['_id']:
            continue

        id_ = article['_id'].replace(" ", "_").replace("*", "")
        encoded = urllib.parse.quote_plus(id_)
        xml_content.append(f"<url><loc>https://headingtomars.com/{ path }/{ encoded }</loc></url>")

    return xml_content


@blueprint.route('/sitemap.xml', methods=['GET', 'POST'])
@api_file_cache(expiration_secs=86400, data_type="xml")
def api_news_generate_sitemap():
    from flask import Response

    ret = {}
    xml = ["<?xml version='1.0' encoding='UTF-8'?><urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"]
    api_news_group_for_sitemap(xml, "publisher", "publisher")
    api_news_group_for_sitemap(xml, "AI.classification", "news/class")
    xml.append("</urlset>")

    xml_content = "".join(xml)

    return Response(xml_content, mimetype='text/xml')

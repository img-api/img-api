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
from api import (admin_login_required, api_key_login_or_anonymous,
                 api_key_or_login_required, cache,
                 get_response_error_formatted, get_response_formatted)
from api.news import blueprint
from api.news.models import DB_News
from api.print_helper import *
from api.query_helper import (build_query_from_request, get_timestamp_verbose,
                              mongo_to_dict_helper, validate_and_convert_dates)
from api.tools.validators import get_validated_email
from flask import Response, abort, jsonify, redirect, request, send_file
from flask_login import current_user
from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q


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


@blueprint.route('/query', methods=['GET', 'POST'])
def api_news_get_query():
    """
    Example of queries: https://dev.gputop.com/api/news/query?related_exchange_tickers=NASDAQ:NVO
    """
    from api.comments.routes import get_comments_count
    from api.gif.sentiment import parse_sentiment

    news = build_query_from_request(DB_News, global_api=True)

    for article in news:
        try:
            if 'ai_summary' in article:
                sentiment, classification = parse_sentiment(article['ai_summary'])
                if sentiment:
                    article['sentiment'] = sentiment
                    article['sentiment_score'] = classification
        except Exception as e:
            print_exception(e, "CRASH")

    clean = request.args.get("cleanup", None)
    if clean and (current_user.is_admin or current_user.username in ["contact@engineer.blue", "admin"]):
        news.delete()
        ret = {'status': "deleted"}
        return get_response_formatted(ret)

    for article in news:
        article['no_comments'] = get_comments_count(str(article.id))

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
    api_create_news_ai_summary(article)

    ret = {'news': [article]}
    return get_response_formatted(ret)


@blueprint.route('/get/<string:news_id>', methods=['GET', 'POST'])
def api_get_news_helper(news_id):
    """ News get ID
    ---
    """
    news = DB_News.objects(id=news_id).first()

    if not news:
        return get_response_error_formatted(404, {'error_msg': "News not found"})

    ret = {'news': [news]}
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


def api_create_news_ai_summary(news, force_summary=False):
    prompt = "Summarize this, and format it max one paragraph, "
    prompt += "use markdown to highlight important facts, "
    prompt += "give a sentiment at the end about the company in the stock market."

    if not news['articles'] or len(news['articles']) == 0:
        return

    if not force_summary and 'ai_summary' in news:
        return

    articles = '\n'.join(news['articles'])

    if "We, Yahoo, are part" in articles:
        print(" FAILED LOADING ARTICLE - REINDEX ")
        news.update(**{"articles": [], "force_reindex": True})
        return

    news.update(**{"ai_upload_date": datetime.now()})

    data = {
        'type': 'summary',
        'id': str(news['id']),
        'prompt': prompt,
        'article': articles,
        'message': prompt + articles,
        'callback_url': "https://tothemoon.life/api/news/ai_callback"
    }

    if 'link' in news:
        data['link'] = news['link']

        print(" UPLOADING TO PROCESS -> " + news['link'])

    if 'source' in news:
        data['source'] = news['source']

    response = requests.post("http://lachati.com:5111/upload-json", json=data)
    response.raise_for_status()

    news.set_state("WAITING_FOR_AI")


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
        api_create_news_ai_summary(item_news, True)

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
    from api.gif.sentiment import parse_sentiment

    json = request.json

    if 'id' not in json:
        return get_response_error_formatted(400, {'error_msg': "An id is required"})

    news = DB_News.objects(id=json['id']).first()

    if not news:
        print_r(" FAILED UPDATING AI " + json['id'])
        return get_response_formatted({})

    if 'type' in json:
        print_b(" NEWS AI_CALLBACK " + json['id'] + " " + str(news.title))

        sentiment = None
        classification = 0

        t = json['type']
        if t == 'dict':
            tools = json['dict']
            ai_summary = json['ai_summary']
            update = {'ai_summary': ai_summary, 'tools': tools}

            try:
                sentiment = tools[0]['function']['arguments']['sentiment']
            except Exception as e:
                print_exception(e, "CRASHED READING SENTIMENT")

            try:
                classification = int(tools[0]['function']['arguments']['sentiment_score'])
            except Exception as e:
                pass

        if t == 'summary':
            ai_summary = json['result']
            update = {'ai_summary': ai_summary}

        if ai_summary and not sentiment:
            sentiment, classification = parse_sentiment(ai_summary)

        if sentiment:
            update['sentiment'] = sentiment
            update['sentiment_score'] = classification

        update['last_visited_date'] = datetime.now()
        news.update(**update)

    ret = {}
    return get_response_formatted(ret)


@blueprint.route('/my_portfolio', methods=['GET', 'POST'])
@api_key_or_login_required
def api_news_my_portfolio_query():
    """
    Builds a query with the current portfolio
    """
    from api.comments.routes import get_comments_count
    from api.ticker.routes import get_watchlist_or_create

    name = request.args.get("name", "default")

    watchlist = get_watchlist_or_create(name)

    ls = str.join(",", watchlist.exchange_tickers)
    extra_args = {'related_exchange_tickers__in': ls}

    news = build_query_from_request(DB_News, global_api=True, extra_args=extra_args)

    for article in news:
        article['no_comments'] = get_comments_count(str(article.id))

    ret = {'news': news}
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

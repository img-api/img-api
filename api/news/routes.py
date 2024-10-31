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
from api.query_helper import build_query_from_request, mongo_to_dict_helper
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

    json = request.json

    if 'id' in json:
        return get_response_error_formatted(400, {'error_msg': "Error, please use UPDATE to update an entry"})

    if 'link' not in json:
        return get_response_error_formatted(400,
                                            {'error_msg': "Missing link, not right format. Please check documentation"})

    article = DB_News(**json)
    article.save()

    ret = {"news": [article]}
    return get_response_formatted(ret)


@blueprint.route('/query', methods=['GET', 'POST'])
def api_news_get_query():
    """
    Example of queries: https://dev.gputop.com/api/news/query?related_exchange_tickers=NASDAQ:NVO
    """
    from .sentiment import parse_sentiment

    news = build_query_from_request(DB_News, global_api=True)

    for article in news:
        if 'ia_summary' not in article:
            continue

        try:
            sentiment, classification = parse_sentiment(article['ia_summary'])
            if sentiment:
                article['sentiment'] = sentiment
                article['sentiment_score'] = classification
        except Exception as e:
            print_exception(e, "CRASH")

    ret = {'news': news}
    return get_response_formatted(ret)


def cleanup_update(article):
    if 'creation_date' in article:
        del article['creation_date']

    if 'last_visited_date' in article:
        del article['last_visited_date']

    return article


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

            article = cleanup_update(article)
            if 'id' in article:
                db_article = DB_News.objects(id=article['id']).first()

            if db_article:
                db_article.update(**article)
            else:
                db_article = DB_News(**article)
                db_article.save(validate=False)

            ret.append(db_article)

    ret = {'news': ret}
    return get_response_formatted(ret)


@blueprint.route('/get/<string:news_id>', methods=['GET', 'POST'])
@blueprint.route('/get/<string:news_id>', methods=['GET', 'POST'])
def api_get_news_helper(news_id):
    """ News get ID
    ---
    """
    if news_id == "ALL":
        news = DB_News.objects()
        ret = {'news': news}
        return get_response_formatted(ret)

    news = DB_News.objects(safe_name=news_id).first()

    if not news:
        return get_response_error_formatted(404, {'error_msg': "News not found"})

    ret = {'news': [news]}
    return get_response_formatted(ret)


@blueprint.route('/rm/<string:article_id>', methods=['GET', 'POST'])
@blueprint.route('/remove/<string:article_id>', methods=['GET', 'POST'])
@api_key_or_login_required
@admin_login_required
def api_remove_a_news_by_id(article_id):
    """ Business deletion
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
def api_get_gif():
    """ """
    from io import BytesIO

    from .sentiment import get_gif_for_sentiment

    keywords = request.args.get("keywords", "SAD")

    raw, gif = get_gif_for_sentiment(keywords)

    raw = request.args.get("raw", None)

    if raw:
        ret = {"keywords": keywords, 'url': gif, 'raw': raw}
        return get_response_formatted(ret)

    response = requests.get(gif)
    if response.status_code != 200:
        return {"error": "Failed to download the gif"}, 500

    # Create a temporary file to store the gif data
    gif_data = BytesIO(response.content)
    return send_file(gif_data, mimetype='image/gif', as_attachment=False, download_name='sentiment.gif')


@blueprint.route('/ai_callback', methods=['GET', 'POST'])
#@api_key_or_login_required
#@admin_login_required
def api_news_callback_ai_summary():
    """ """
    from .sentiment import parse_sentiment

    json = request.json

    news = DB_News.objects(id=json['id']).first()

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
    from api.ticker.routes import get_watchlist_or_create

    name = request.args.get("name", "default")

    watchlist = get_watchlist_or_create(name)

    ls = str.join(",", watchlist.exchange_tickers)
    extra_args = {'related_exchange_tickers__in': ls}

    news = build_query_from_request(DB_News, global_api=True, extra_args=extra_args)

    ret = {'news': news}
    return get_response_formatted(ret)

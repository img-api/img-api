import io
import random
import re
import time
from datetime import datetime

import requests
from api import (admin_login_required, api_key_login_or_anonymous,
                 api_key_or_login_required, cache,
                 get_response_error_formatted, get_response_formatted)
from api.print_helper import *
from api.prompts import blueprint
from api.prompts.models import DB_UserPrompt
from api.query_helper import (build_query_from_request, get_timestamp_verbose,
                              mongo_to_dict_helper, validate_and_convert_dates)
from api.tools.markdownify import markdownify
from flask import Response, abort, jsonify, redirect, request, send_file
from flask_login import current_user
from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q


@blueprint.route('/create', methods=['GET', 'POST'])
@api_key_or_login_required
def api_create_prompt_local():
    """ Create a new prompt to be resolved
    ---
    """

    print("======= CREATE A SINGLE PROMPT =============")

    jrequest = request.json

    if 'id' in jrequest:
        return get_response_error_formatted(400, {'error_msg': "Error, please use UPDATE to update an entry"})

    jrequest['prompt'] = markdownify(jrequest['prompt']).strip()
    jrequest['status'] = "INDEX"

    prompt = DB_UserPrompt(**jrequest)
    prompt.save()

    ret = {"prompts": [prompt]}
    return get_response_formatted(ret)


@blueprint.route('/query', methods=['GET', 'POST'])
def api_prompt_get_query():
    """

    """
    extra_args = None

    prompts = build_query_from_request(DB_UserPrompt, global_api=False, extra_args=extra_args)

    ret = {'prompts': prompts}
    return get_response_formatted(ret)


@blueprint.route('/get/<string:prompt_id>', methods=['GET', 'POST'])
def api_get_prompt_helper(prompt_id):
    """ Prompt ID
    ---
    """
    news = DB_UserPrompt.objects(id=prompt_id).first()

    if not news:
        return get_response_error_formatted(404, {'error_msg': "User prompt not found"})

    ret = {'prompts': [prompts]}
    return get_response_formatted(ret)


@blueprint.route('/rm/<string:prompt_id>', methods=['GET', 'POST'])
@blueprint.route('/remove/<string:prompt_id>', methods=['GET', 'POST'])
@api_key_or_login_required
@admin_login_required
def api_remove_a_prompt_by_id(prompt_id):
    """ Prompt deletion
    ---
    """

    # CHECK API ONLY ADMIN
    if prompt_id == "ALL":
        prompt_id.objects().delete()
        ret = {'status': "deleted"}
        return get_response_formatted(ret)

    prompts = DB_UserPrompt.objects(id=prompt_id).first()

    if not prompts:
        return get_response_error_formatted(404, {'error_msg': "The prompt was not found for the current user"})

    ret = {'status': "deleted", 'prompts': prompts}

    prompts.delete()
    return get_response_formatted(ret)


@blueprint.route('/rm', methods=['GET', 'POST'])
def api_remove_a_prompt_by_id_request():
    prompt_id = request.args.get("id", None)
    return api_remove_a_news_by_id(prompt_id)


def api_create_prompt_ai_summary(db_prompt):

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


@blueprint.route('/ai_callback', methods=['GET', 'POST'])
#@api_key_or_login_required
#@admin_login_required
def api_prompt_callback_ai_summary():
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

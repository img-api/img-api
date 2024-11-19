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

    db_prompt = DB_UserPrompt(**jrequest)
    db_prompt.save()

    priority = False
    try:
        if current_user.subscription.status == "active":
            priority = True

    except Exception as e:
        pass

    res = api_create_prompt_ai_summary(db_prompt, priority)
    ret = {"prompts": [db_prompt]}

    if 'queue_size' in res:
        ret['queue_size'] = res['queue_size']

    return get_response_formatted(ret)


@blueprint.route('/query', methods=['GET', 'POST'])
@api_key_or_login_required
def api_prompt_get_query():
    """

    """
    extra_args = None

    prompts = build_query_from_request(DB_UserPrompt, global_api=False, append_public=False, extra_args=extra_args)

    ret = {'prompts': prompts}
    return get_response_formatted(ret)


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

    # CHECK API ONLY ADMIN
    if prompt_id == "ALL":
        res = DB_UserPrompt.objects()
        ret = {'status': "deleted", 'prompts': res}
        res.delete()
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
    return api_remove_a_prompt_by_id(prompt_id)


@blueprint.route('/ai_callback', methods=['GET', 'POST'])
#@api_key_or_login_required
#@admin_login_required
def api_prompt_callback_ai_summary():
    json = request.json

    if 'id' not in json:
        return get_response_error_formatted(400, {'error_msg': "An id is required"})

    db_prompt = DB_UserPrompt.objects(id=json['id']).first()

    if not db_prompt:
        print_r(" FAILED UPDATING AI " + json['id'])
        return get_response_formatted({})

    if 'type' in json:
        print_b(" NEWS AI_CALLBACK " + json['id'] + " " + str(db_prompt.prompt))

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

        update['last_visited_date'] = datetime.now()
        update['status'] = "PROCESSED"
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


def api_create_prompt_ai_summary(db_prompt, priority=False, force_summary=False):
    prompt = ""

    prompt += db_prompt.prompt

    data = {
        'type': 'user_prompt',
        'id': str(db_prompt.id),
        'prompt': prompt,
        'article': "DUMP TEST ARTICLE, SORRY AI",
        'callback_url': "https://tothemoon.life/api/prompts/ai_callback"
    }

    if priority:
        data['priority'] = priority

    response = requests.post("https://singapore.lachati.com/api_v1/upload-json", json=data)
    response.raise_for_status()

    try:
        json_response = response.json()
        print_json(json_response)

        return json_response
    except Exception as e:
        print_exception(e, "CRASH READING RESPONSE")

    return {}


@blueprint.route('/state', methods=['GET', 'POST'])
@api_key_or_login_required
@admin_login_required
def api_llama_get_state():
    response = requests.post("https://singapore.lachati.com/api_v1/")
    response.raise_for_status()

    try:
        json_response = response.json()
        print_json(json_response)

        return json_response
    except Exception as e:
        print_exception(e, "CRASH READING RESPONSE")

    return {}


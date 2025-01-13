import socket
from datetime import datetime, timedelta

import mistune
import requests
from api import (admin_login_required, api_key_or_login_required,
                 get_response_error_formatted, get_response_formatted, mail)
from api.config import (get_api_AI_service, get_api_entry, get_config_sender,
                        get_config_value, get_host_name, is_api_development)
from api.print_helper import *
from api.prompts.models import DB_UserPrompt
from api.query_helper import *
from api.telegram import blueprint
from api.telegram.models import DB_TelegramMessageQueue
from api.user.models import User
from bson.objectid import ObjectId
from flask import Flask, json, jsonify, redirect, request
from flask_login import AnonymousUserMixin, current_user
from mongoengine import *
from mongoengine.errors import ValidationError


@blueprint.route('/register/<string:user_id>/<string:chat_id>', methods=['GET', 'POST'])
@api_key_or_login_required
@admin_login_required
def api_user_save_telegram_chat_id(user_id, chat_id):
    db_user = User.objects(id=user_id).first()
    db_user.update(**{'my_telegram_chat_id': chat_id})
    db_user.reload()

    return get_response_formatted({'user': db_user, 'my_telegram_chat_id': chat_id})


@blueprint.route('/who/<string:chat_id>', methods=['GET', 'POST'])
@api_key_or_login_required
@admin_login_required
def api_user_search_telegram_chat_id(chat_id):
    db_user = User.objects(my_telegram_chat_id=chat_id).first()
    return get_response_formatted({'user': db_user.serialize()})


def api_create_telegram_chat(db_user, prompt, chat_data={}):
    from api.news.routes import get_portfolio_query
    from api.prompts.routes import (api_create_content_from_news,
                                    api_create_content_from_tickers,
                                    cut_string)

    news, tkrs = get_portfolio_query(my_args={'reversed': 1}, username=db_user.username)
    tickers = api_create_content_from_tickers(tkrs)
    content = api_create_content_from_news(news)

    #if db_prompt:
    #    tickers += f"Previous chats: { db_prompt['ai_summary'] }\n"

    system = "Today is " + str(datetime.now().strftime("%Y/%m/%d, %H:%M")) + "\n"
    system += "The user is " + db_user.first_name + " " + db_user.last_name + "\n"
    system += "Your name is Isabella, you are an expert that can provide financial advice due regulations in the country.\n"
    system += "Use markdown and unicode emojis and icons as extra output for the text to be well formatted."

    assistant = cut_string(tickers + content, 256000)
    assistant += ". Use markdown and unicode emojis and icons as extra output for the text to be well formatted."

    data = {
        'type': 'user_prompt',
        'prompt': prompt,
        'system': system,
        'assistant': assistant,
        'status': "WAITING_AI",
        'use_markdown': True,
        'username': db_user.username,
        'hostname': socket.gethostname()
    }

    data.update(chat_data)

    if is_api_development():
        data['dev'] = True

    db_prompt = DB_UserPrompt(**data)
    db_prompt.save(is_admin=True)

    data['id'] = str(db_prompt.id)
    data['prefix'] = "0_CHAT_" + db_prompt.username
    data['callback_url'] = get_api_entry() + "/telegram/ai_callback"
    data['priority'] = 1

    try:
        response = requests.post(get_api_AI_service(), json=data)
        response.raise_for_status()

        json_response = response.json()
        print_json(json_response)

        db_prompt.update(**{
            'ai_upload_date': datetime.now(),
            'ai_queue_size': json_response['queue_size']
        },
                         is_admin=True)

    except Exception as e:
        db_prompt.update(**{
            'ai_summary': "SORRY SOMETHING WENT WRONG, IT IS NOT YOU, IT IS ME",
            'status': "FAILED",
        })
        print_exception(e, "CRASH READING RESPONSE")

    return data, db_prompt


@blueprint.route('/chat/<string:chat_id>', methods=['POST'])
@api_key_or_login_required
@admin_login_required
def api_user_telegram_chat(chat_id):
    json = request.json

    db_user = User.objects(my_telegram_chat_id=chat_id).first()

    #ret = {'user': db_user.serialize()}
    #ret['message_id'] = json['message_id']
    #ret['reply'] = "Reply hello world!"

    api_create_telegram_chat(db_user, json['text'], json)

    ret = {}
    return get_response_formatted(ret)


@blueprint.route('/ai_callback', methods=['GET', 'POST'])
def api_telegram_callback_ai_summary():
    json = request.json

    if 'id' not in json:
        return get_response_error_formatted(400, {'error_msg': "An id is required"})

    db_prompt = DB_UserPrompt.objects(id=json['id']).first()

    if not db_prompt:
        print_r("PROMPT FAILED UPDATING AI " + json['id'])
        return get_response_formatted({})

    if 'type' in json:
        print_b(" TELEGRAM CHAT AI_CALLBACK " + json['id'] + " " + str(db_prompt.prompt))

        update = {}

        t = json['type']
        if t == 'dict':
            tools = json['dict']
            ai_summary = json['ai_summary']
            update = {'ai_summary': ai_summary, 'tools': tools}

        if t == 'user_prompt':
            update = {'ai_summary': json['result']}

        update['last_visited_date'] = datetime.now()
        update['last_visited_verbose'] = datetime.now().strftime("%Y/%m/%d, %H:%M:%S")

        if is_api_development():
            update['dev'] = True

        update['status'] = "WAITING_TELEGRAM"

        if 'raw' in json:
            update['raw'] = json['raw']

        if 'raw_tools' in json:
            update['raw_tools'] = json['raw_tools']

        db_prompt.update(**update, is_admin=True)

    ret = {}
    return get_response_formatted(ret)


@blueprint.route('/polling', methods=['GET', 'POST'])
@api_key_or_login_required
@admin_login_required
def api_telegram_callback_polling():
    is_telegram = request.args.get("telegram", None)

    ret = []

    prompts = DB_UserPrompt.objects(status="WAITING_TELEGRAM")
    for db_prompt in prompts:
        if not db_prompt.chat_id:
            db_prompt.update(**{'status': "MISSING CHANNEL"}, is_admin=True)
            continue

        result = {
            'chat_id': db_prompt.chat_id,
            'message_id': db_prompt.message_id,
            'reply': db_prompt.ai_summary,
        }

        ret.append(result)

        if is_telegram:
            update = {'status': "SENT_TO_TELEGRAM"}
            db_prompt.update(**update, is_admin=True)

    db_messages = DB_TelegramMessageQueue.objects(status="WAIT_QUEUE")
    for db_msg in db_messages:
        if not db_msg.chat_id:
            db_msg.update(**{'status': "MISSING CHANNEL"})
            continue

        result = {
            'chat_id': db_msg.chat_id,
            'reply': db_msg.title + " " + db_msg.message,
        }

        ret.append(result)

        if is_telegram:
            update = {'status': "SENT_TO_TELEGRAM"}
            db_msg.update(**update)

    return get_response_formatted({'messages': ret})


def api_telegram_create_message(user, title, message, image_id=None):

    if not user.my_telegram_chat_id:
        print_r(f" { user.username } Missing chat id ")
        return

    now = datetime.now()
    data = {
        'title': title,
        'message': message,
        'creation_date': now,
        'last_update_date': now,
        'username': user.username,
        'chat_id': str(user.my_telegram_chat_id),
    }

    db_msg_queue = DB_TelegramMessageQueue(**data)
    db_msg_queue.save()

    return db_msg_queue

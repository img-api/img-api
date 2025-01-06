import socket
from datetime import datetime, timedelta

import mistune
import requests
from api import (admin_login_required, api_key_or_login_required,
                 get_response_error_formatted, get_response_formatted, mail)
from api.config import (get_api_AI_service, get_api_entry, get_host_name,
                        is_api_development)
from api.print_helper import *
from api.prompts.models import DB_UserPrompt
from api.query_helper import *
from api.telegram import blueprint
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
    db_user.update(**{'telegram_chat_id': chat_id})
    db_user.reload()

    return get_response_formatted({'user': db_user, 'telegram_id': id})

import time
import random
import bcrypt
import binascii

import validators

from api.content import blueprint
from api.print_helper import *

from api import get_response_formatted, get_response_error_formatted, api_key_or_login_required, api_key_login_or_anonymous, cache

from flask import jsonify, request, Response, redirect, abort
from api.tools import generate_file_md5, ensure_dir, is_api_call
from api.query_helper import mongo_to_dict_helper

from .models import DB_UserContent

from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q

from flask_login import current_user, login_user, logout_user


@blueprint.route('/<string:my_section>/set/<string:my_key>', methods=['GET', 'POST'])
@api_key_or_login_required
def api_set_content_key(my_section, my_key):
    """ Sets this content variable """

    value = request.args.get("value", None)
    if not value and 'value' in request.json:
        value = request.json['value']

    if value == None:
        return get_response_error_formatted(400, {'error_msg': "Wrong parameters."})

    value = clean_html(value)

    if not content.set_key_value(my_key, value):
        return get_response_error_formatted(400, {'error_msg': "Something went wrong saving this key."})

    ret = content.serialize()
    return get_response_formatted(ret)


@blueprint.route('/<string:my_section>/update', methods=['GET', 'POST'])
@api_key_or_login_required
def api_update_content(my_section):
    """ Sets this content variable """

    data = request.json
    for key in data:
        if len(data[key]) > 4 * 4096:
            return get_response_error_formatted(400, {'error_msg': "Too much content!"})

        data[key] = clean_html(data[key])

    data['section'] = my_section
    data['username'] = current_user.username

    content = DB_UserContent.objects(Q(username=current_user.username) & Q(section=my_section)).first()
    if not content:
        # TODO: Check the amount of content the user has, and do not let users save more than that.

        content = DB_UserContent(**data)
        content.save()
    else:
        content.update(**data, validate=False)

    return get_response_formatted({my_section: content.serialize()})


@blueprint.route('/<string:my_section>/get', methods=['GET', 'POST'])
@api_key_or_login_required
def api_get_content(my_section):
    """ Gets this content variable """

    content = DB_UserContent.objects(Q(username=current_user.username) & Q(section=my_section)).first()
    if not content:
        return get_response_formatted({my_section: {}})

    return get_response_formatted({my_section: content.serialize()})
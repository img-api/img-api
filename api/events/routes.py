import io
import os
import time
import ffmpeg
import validators

from datetime import datetime

from api import sanitizer
from api.events import blueprint
from api.api_redis import api_rq

from api import get_response_formatted, get_response_error_formatted, api_key_or_login_required, api_key_login_or_anonymous, cache
from flask import jsonify, request, send_file, redirect

from flask import current_app, url_for, abort
from api.print_helper import *

from api.tools import generate_file_md5, ensure_dir, is_api_call
from api.user.routes import generate_random_user
from .models import DB_Event

from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q
from api.query_helper import mongo_to_dict_helper, build_query_from_request


@blueprint.route('/query', methods=['GET', 'POST'])
@api_key_or_login_required
def api_get_query():
    from flask_login import current_user
    """
    """

    events = build_query_from_request(DB_Event)

    ret = {'status': 'success', 'events': events}
    return get_response_formatted(ret)


@blueprint.route('/<string:event_id>/get', methods=['GET', 'POST'])
@api_key_or_login_required
def api_get_event(event_id):
    from flask_login import current_user
    """
    """

    if event_id == "all":
        if current_user.username == "admin":
            events = DB_Event.objects()
        else:
            events = DB_Event.objects(username=current_user.username)

        ret = {'status': 'success', 'event_id': event_id, 'events': events}
        return get_response_formatted(ret)

    q = Q(username=current_user.username) & Q(id=event_id)
    event = DB_Event.objects(q).first()

    ret = {'status': 'success', 'event_id': event_id, 'event': event}
    return get_response_formatted(ret)


@blueprint.route('/<string:event_id>/set/<string:my_key>', methods=['GET', 'POST'])
@api_key_or_login_required
def api_set_event_key(event_id, my_key):
    from flask_login import current_user  # Required by pytest, otherwise client crashes on CI

    event = DB_Event.objects(id=event_id).first()

    if not event:
        return get_response_error_formatted(404, {'error_msg': "Missing."})

    if not event.is_current_user():
        return get_response_error_formatted(403, {'error_msg': "This user is not allowed to perform this action."})

    value = request.args.get("value", None)
    if not value:
        if hasattr(request, "json") and 'value' in request.json:
            value = request.json['value']

    if value == None:
        return get_response_error_formatted(400, {'error_msg': "Wrong parameters."})

    value = clean_html(value)
    event.set_key_value(my_key, value)

    ret = {'status': 'success', 'event_id': event_id, 'event': event}
    return get_response_formatted(ret)


@blueprint.route('/<string:event_id>/rm', methods=['GET', 'POST'])
@api_key_or_login_required
def api_remove_event(event_id):
    from flask_login import current_user
    """
    """

    if event_id == "all":
        if current_user.username == "admin":
            events = DB_Event.objects()
        else:
            events = DB_Event.objects(username=current_user.username)

        events.delete()
        ret = {'status': 'success', 'event_id': event_id, 'events': events}
        return get_response_formatted(ret)

    q = Q(username=current_user.username) & Q(id=event_id)
    event = DB_Event.objects(q).first()
    event.delete()

    ret = {'status': 'success', 'event_id': event_id, 'event': event}
    return get_response_formatted(ret)


@blueprint.route('/create', methods=['POST'])
@api_key_or_login_required
def api_create_event():
    from flask_login import current_user

    if (ctype := request.headers.get('Content-Type')) != 'application/json':
        return get_response_error_formatted(400, {'error_msg': "Wrong call."})

    json_ = request.json

    event = DB_Event(**json_)
    event.save(validate=False)

    ret = {'status': 'success', 'event': mongo_to_dict_helper(event)}
    return get_response_formatted(ret)

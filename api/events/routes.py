

from api import (api_key_or_login_required, get_response_error_formatted,
                 get_response_formatted)
from api.events import blueprint
from api.print_helper import *
from api.query_helper import build_query_from_request, mongo_to_dict_helper
from flask import request
from mongoengine.queryset.visitor import Q

from .models import DB_Event


@blueprint.route('/query', methods=['GET', 'POST'])
@api_key_or_login_required
def api_get_query():
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
    from flask_login import \
        current_user  # Required by pytest, otherwise client crashes on CI

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
    pass

    if (ctype := request.headers.get('Content-Type')) != 'application/json':
        return get_response_error_formatted(400, {'error_msg': "Wrong call."})

    json_ = request.json

    event = DB_Event(**json_)
    event.save(validate=False)

    ret = {'status': 'success', 'event': mongo_to_dict_helper(event)}
    return get_response_formatted(ret)

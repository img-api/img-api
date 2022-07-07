import io
import os
import time
import json
import ffmpeg
import datetime
import validators

from api.actors import blueprint
from api.api_redis import api_rq

from api import get_response_formatted, get_response_error_formatted, api_key_or_login_required, api_key_login_or_anonymous, cache, sanitizer

from flask import jsonify, request, send_file, redirect
from flask import current_app, url_for, abort

from api.print_helper import *
from api.tools import generate_file_md5, ensure_dir, is_api_call, to_bytes

from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q

from api.query_helper import mongo_to_dict_helper, mongo_to_dict_result


@blueprint.route('/update', methods=['POST'])
@api_key_or_login_required
def api_update_a_media():
    """ Updates an actor """

    from flask_login import current_user  # Required by pytest, otherwise client crashes on CI

    json = request.json
    if not current_user.is_authenticated:
        return abort(404, "User is not valid")

    my_file = File_Tracking.objects(pk=json['media_id']).first()
    if not my_file:
        return abort(404, "Media is not valid")

    ret = my_file.update_with_checks(json)
    if not ret:
        return abort(400, "You cannot edit this library")

    ret['username'] = current_user.username

    return get_response_formatted(ret)

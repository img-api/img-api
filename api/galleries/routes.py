import io
import os
import time
import json
import ffmpeg
import datetime
import validators

from api.galleries import blueprint
from api.api_redis import api_rq

from api import get_response_formatted, get_response_error_formatted, api_key_or_login_required, api_key_login_or_anonymous, cache, sanitizer
from flask import jsonify, request, send_file, redirect

from flask import current_app, url_for, abort
from api.print_helper import *

from api.tools import generate_file_md5, ensure_dir, is_api_call
from api.user.routes import generate_random_user

from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q

from flask_cachecontrol import (cache, cache_for, dont_cache, Always, ResponseIsSuccessfulOrRedirect)
from api.galleries.models import DB_MediaList
from api.query_helper import mongo_to_dict_helper, mongo_to_dict_result


@blueprint.route('<string:gallery_type>/get', methods=['GET'])
@api_key_login_or_anonymous
#@cache_for(hours=48, only_if=ResponseIsSuccessfulOrRedirect)
def api_get_galleries(gallery_type):
    """Returns a list of galleries to be displayed, with the current query

    ---
    tags:
      - media
    schemes: ['http', 'https']
    deprecated: false
    definitions:
      image_file:
        type: object
    parameters:
        - in: query
          name: thumbnail
          schema:
            type: string
          description: You can specify a Thumbnail size that will correct the aspect ratio Examples .v256.PNG or .h128.GIF

    responses:
      200:
        description: Returns a file or a generic placeholder for the file
      404:
        description: Galleries don't exist on this group

    """

    the_list = DB_MediaList.objects(is_public=True).exclude('media_list')
    if not the_list:
        return abort(404, "No public galleries")

    galleries = mongo_to_dict_result(the_list)

    ret = {'galleries': galleries}

    return get_response_formatted(ret)
import io
import os
import time
import ffmpeg
import datetime
import validators

from api.media import blueprint
from api.api_redis import api_rq

from api import get_response_formatted, get_response_error_formatted, api_key_or_login_required, api_key_login_or_anonymous, cache
from flask import jsonify, request, send_file, redirect

from flask import current_app, url_for, abort
from api.print_helper import *

from api.tools import generate_file_md5, ensure_dir, is_api_call
from api.user.routes import generate_random_user
from .models import File_Tracking

from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q

@blueprint.route('/get/<string:category>', methods=['GET'])
def api_get_tags(category):
    """
        Tags are added to galleries, and media

        Tags are classified in categories

    """


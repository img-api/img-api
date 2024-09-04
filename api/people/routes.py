import io
import os
import time
import json
import ffmpeg

import validators

from api.people import blueprint

from api import get_response_formatted, get_response_error_formatted, api_key_or_login_required, api_key_login_or_anonymous, cache

from flask import jsonify, request, send_file, redirect
from flask import current_app, url_for, abort

from api.print_helper import *

from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q

from api.query_helper import mongo_to_dict_helper, build_query_from_request
from .models import DB_People


@blueprint.route('/query', methods=['GET', 'POST'])
#@api_key_or_login_required
def api_people_get_query():
    """
    Example of queries: https://dev.gputop.com/api/people/query?year_born=1994
    """

    people = build_query_from_request(DB_People, global_api=True)

    ret = {'people': people}
    return get_response_formatted(ret)

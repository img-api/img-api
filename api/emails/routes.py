import io
import re
import time
import random
import bcrypt
import binascii

import validators

import qrcode
from api.news import blueprint
from api.print_helper import *

from api import get_response_formatted, get_response_error_formatted, api_key_or_login_required, api_key_login_or_anonymous, cache
from flask import jsonify, request, Response, redirect, abort, send_file
from flask_login import current_user

from api.news.models import DB_News

from api.emails.models import DB_News

from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q

from api.query_helper import mongo_to_dict_helper, build_query_from_request

from api.tools.validators import get_validated_email


@blueprint.route('/query', methods=['GET', 'POST'])
#@api_key_or_login_required
def api_email_store_get_query():
    """
    Example of queries: https://dev.gputop.com/api/news/query?related_exchange_tickers=NASDAQ:NVO
    """

    store = build_query_from_request(DB_EmailStore, global_api=True)

    ret = {'status': 'success', 'estore': store}
    return get_response_formatted(ret)

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

from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q

from api.query_helper import mongo_to_dict_helper, build_query_from_request

from api.tools.validators import get_validated_email


@blueprint.route('/query', methods=['GET', 'POST'])
#@api_key_or_login_required
def api_news_get_query():
    """
    Example of queries: https://dev.gputop.com/api/news/query?related_exchange_tickers=NASDAQ:NVO
    """

    news = build_query_from_request(DB_News, global_api=True)

    ret = {'status': 'success', 'news': news}
    return get_response_formatted(ret)


@blueprint.route('/get/<string:news_id>', methods=['GET', 'POST'])
@blueprint.route('/get/<string:news_id>', methods=['GET', 'POST'])
def api_get_news_helper(news_id):
    """ News get ID
    ---
    """
    if news_id == "ALL":
        news = DB_News.objects()
        ret = {'news': news}
        return get_response_formatted(ret)

    news = DB_News.objects(safe_name=biz_name).first()

    if not news:
        return get_response_error_formatted(404, {'error_msg': "News not found"})

    ret = {'news': [news]}
    return get_response_formatted(ret)


@blueprint.route('/rm/<string:biz_id>', methods=['GET', 'POST'])
@blueprint.route('/remove/<string:biz_id>', methods=['GET', 'POST'])
def api_remove_a_news_by_id(biz_id):
    """ Business deletion
    ---
    """

    # CHECK API ONLY ADMIN
    if biz_id == "ALL":
        DB_News.objects().delete()
        ret = {'status': "deleted"}
        return get_response_formatted(ret)

    news = DB_News.objects(id=biz_id).first()

    if not news:
        return get_response_error_formatted(404, {'error_msg': "News article not found for the current user"})

    ret = {'status': "deleted", 'news': news.serialize()}

    news.delete()
    return get_response_formatted(ret)

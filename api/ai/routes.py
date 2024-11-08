import binascii
import io
import random
import re
import time

import requests
from api import (api_key_login_or_anonymous, api_key_or_login_required, cache, get_response_error_formatted,
                 get_response_formatted)
from api.ai import blueprint
from api.ai.models import DB_AI_Process
from api.company.models import DB_Company
from api.print_helper import *
from api.query_helper import build_query_from_request
from flask import Response, abort, jsonify, redirect, request, send_file
from flask_login import current_user
from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q


@blueprint.route('/query', methods=['GET', 'POST'])
@api_key_or_login_required
def api_company_get_query():
    """
    Example of queries:
    """
    ai_process = build_query_from_request(DB_AI_Process, global_api=True)

    ret = {'ai_process': ai_process}
    return get_response_formatted(ret)


@blueprint.route('/ai_summary', methods=['GET', 'POST'])
#@api_key_or_login_required
def api_company_get_ai_summary():
    """
        https://gputop.com/api/company/ai_summary?exchange_tickers=NASDAQ:INTC

    """
    index_all = request.args.get("index_all", None)

    companies = build_query_from_request(DB_Company, global_api=True)

    for company in companies:
        api_create_ai_summary(company, True)

    ret = {'companies': companies}
    return get_response_formatted(ret)


@blueprint.route('/ai_callback', methods=['GET', 'POST'])
#@api_key_or_login_required
def api_company_callback_ai_summary():
    """ """
    json = request.json

    business = DB_Company.objects(safe_name=json['id']).first()

    if 'type' in json:

        print_b(" AI_CALLBACK " + json['id'])

        t = json['type']
        if t == 'dict':
            functions = {'tools': json['dict']}
            business.update(**functions)
        elif t == 'summary':
            business.set_key_value('ai_summary', json['result'])

    ret = {}
    return get_response_formatted(ret)

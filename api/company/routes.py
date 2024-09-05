import binascii
import io
import random
import re
import time

import bcrypt
import qrcode
import validators
from api import (api_key_login_or_anonymous, api_key_or_login_required, cache,
                 get_response_error_formatted, get_response_formatted)
from api.company import blueprint
from api.company.models import DB_Company
from api.print_helper import *
from api.query_helper import build_query_from_request, mongo_to_dict_helper
from api.tools.validators import get_validated_email
from flask import Response, abort, jsonify, redirect, request, send_file
from flask_login import current_user
from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q


@blueprint.route('/query', methods=['GET', 'POST'])
#@api_key_or_login_required
def api_company_get_query():
    """
    Example of queries: https://dev.gputop.com/api/company/query?founded=1994
    """

    companies = build_query_from_request(DB_Company, global_api=True)

    ret = {'status': 'success', 'companies': companies}
    return get_response_formatted(ret)


def company_get_suggestions(text, only_tickers=False):
    """ """

    # Don't destroy the database
    if only_tickers and len(text) < 3:
        return []

    if len(text) > 3:
        query = Q(company_name__icontains=text)
    else:
        query = Q(company_name__istartswith=text)

    if len(text) <= 4:
        query = query | Q(exchange_tickers__icontains=text)

    companies = DB_Company.objects(query)

    if only_tickers:
        tickers = []
        for rec in companies:
            print(" Rec " + rec.company_name)
            for i in rec.exchange_tickers:
                tickers.append(i)

        return tickers

    return companies


@blueprint.route('/suggestions', methods=['GET', 'POST'])
#@api_key_or_login_required
def api_company_get_suggestions():
    """ """
    query = request.args.get("query", "").upper()
    if not query:
        ret = {'status': 'success', 'suggestions': []}
        return get_response_formatted(ret)

    suggs = company_get_suggestions(query)

    #extra = [{"company_name": rec.company_name, "exchange_tickers": rec.exchange_tickers} for rec in suggs]
    extra = [rec.exchange_tickers for rec in suggs]

    suggestions = [rec.company_name for rec in suggs]
    ret = {'suggestions': suggestions, 'extra': extra}
    return get_response_formatted(ret)


@blueprint.route('/create', methods=['GET', 'POST'])
#@api_key_or_login_required
def api_create_business_for_user_local():
    """ Business creation
    ---
    """

    print("======= CREATE Company Local =============")

    json = request.json
    business = DB_Company(**json)
    business.save()

    return get_response_formatted(business.serialize())


@blueprint.route('/rm/<string:biz_id>', methods=['GET', 'POST'])
@blueprint.route('/remove/<string:biz_id>', methods=['GET', 'POST'])
def api_remove_a_business_by_id(biz_id):
    """ Business deletion
    ---
    """

    # CHECK API ONLY ADMIN
    if biz_id == "ALL":
        DB_Company.objects().delete()
        ret = {'status': "deleted"}
        return get_response_formatted(ret)

    business = DB_Company.objects(id=biz_id).first()

    if not business:
        return get_response_error_formatted(404, {'error_msg': "Business not found for the current user"})

    ret = {'status': "deleted", 'company': business.serialize()}

    business.delete()
    return get_response_formatted(ret)


@blueprint.route('/get/<string:biz_name>', methods=['GET', 'POST'])
@blueprint.route('/get/<string:biz_name>', methods=['GET', 'POST'])
def api_get_business_info(biz_name):
    """ Business get info
    ---
    """
    if biz_name == "ALL":
        business = DB_Company.objects()

        result_array = [item.serialize() for item in business]
        ret = {'company': result_array}
        return get_response_formatted(ret)

    business = DB_Company.objects(safe_name=biz_name).first()

    if not business:
        return get_response_error_formatted(404, {'error_msg': "Business not found"})

    ret = {'company': business.serialize()}
    return get_response_formatted(ret)


@blueprint.route('/get_stamp/<string:biz_name>', methods=['GET', 'POST'])
def api_get_new_stamp(biz_name):
    """ Business get new stamp
    ---
    """

    from cryptography.fernet import Fernet

    business = DB_Company.objects(safe_name=biz_name).first()

    if not business:
        return get_response_error_formatted(404, {'error_msg': "Business not found"})

    stamp = business.get_new_stamp()
    content = request.url_root + "api/biz/stamp/" + biz_name + "/" + stamp

    print(content)

    img = qrcode.make(content)
    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)
    return send_file(buf, mimetype='image/jpeg')


@blueprint.route('/stamp/<string:biz_name>/<string:encrypted_date>', methods=['GET', 'POST'])
def api_apply_stamp(biz_name, encrypted_date):
    """ Business stamp an user
    ---
    """

    business = DB_Company.objects(safe_name=biz_name).first()

    if not business:
        return get_response_error_formatted(404, {'error_msg': "Business not found"})

    stamp = business.decode_stamp(encrypted_date)

    ret = {
        'result': "OK",
        'stamp_age_sec': stamp,
        'company': business.serialize(),
    }

    if stamp > 300:
        ret['result'] = "EXPIRED STAMP"

        ret.update({'error_msg': "Stamp expired and is GONE"})
        return get_response_error_formatted(410, ret)

    # Find user if there is an user

    # Increment the stamps amount

    #

    return get_response_formatted(ret)


@blueprint.route('/categories', methods=['GET', 'POST'])
def company_explorer_categories():
    exchange = request.args.get("exchange", "").upper()
    group = request.args.get("group", "gics_sector")

    gics_sector = request.args.get("gics_sector", None)

    pipeline = []
    if gics_sector:
        match_exchange = {
            "$match": {
                "gics_sector": gics_sector,
            }
        }

        pipeline.append(match_exchange)

    elif exchange:
        match_exchange = {
            "$match": {
                "exchanges": exchange,
            }
        }

        pipeline.append(match_exchange)

    pipeline.append({"$group": {"_id": "$" + group, "count": {"$sum": 1}}})
    pipeline.append({"$sort": {"_id": 1}})

    ret = {}

    ret['result'] = list(DB_Company.objects.aggregate(*pipeline))
    ret['pipeline'] = [pipeline]

    return get_response_formatted(ret)

import io
import re
import time
import random
import bcrypt
import binascii

import validators

import qrcode
from api.business import blueprint
from api.print_helper import *

from api import get_response_formatted, get_response_error_formatted, api_key_or_login_required, api_key_login_or_anonymous, cache, sanitizer
from flask import jsonify, request, Response, redirect, abort, send_file
from flask_login import current_user

from api.business.models import DB_Business

from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q

from api.tools.validators import get_validated_email


@blueprint.route('/create', methods=['GET', 'POST'])
def api_create_business_for_user_local():
    """ Business creation
    ---
    """

    print("======= CREATE Business Local =============")

    json = request.json

    biz_email = get_validated_email(json['email'])
    if isinstance(biz_email, Response):
        return biz_email

    json.update({
        'email': biz_email,
        'username': current_user.username,
    })

    business = DB_Business(**json)
    business.save()

    return get_response_formatted(business.serialize())


@blueprint.route('/rm/<string:biz_id>', methods=['GET', 'POST'])
@blueprint.route('/remove/<string:biz_id>', methods=['GET', 'POST'])
def api_remove_a_business_by_id(biz_id):
    """ Business deletion
    ---
    """

    business = DB_Business.objects(username=current_user.username, id=biz_id).first()

    if not business:
        return get_response_error_formatted(404, {'error_msg': "Business not found for the current user"})

    ret = {'status': "deleted", 'business': business.serialize()}

    business.delete()
    return get_response_formatted(ret)


@blueprint.route('/get/<string:username>/<string:biz_name>', methods=['GET', 'POST'])
@blueprint.route('/get/<string:username>/<string:biz_name>', methods=['GET', 'POST'])
def api_get_business_info(username, biz_name):
    """ Business get info
    ---
    """

    business = DB_Business.objects(username=username, safe_name=biz_name).first()

    if not business:
        return get_response_error_formatted(404, {'error_msg': "Business not found"})

    ret = {'business': business.serialize()}
    return get_response_formatted(ret)


@blueprint.route('/get_stamp/<string:username>/<string:biz_name>', methods=['GET', 'POST'])
def api_get_new_stamp(username, biz_name):
    """ Business get new stamp
    ---
    """

    from cryptography.fernet import Fernet

    business = DB_Business.objects(username=username, safe_name=biz_name).first()

    if not business:
        return get_response_error_formatted(404, {'error_msg': "Business not found"})

    stamp = business.get_new_stamp()
    content = request.url_root + "api/biz/stamp/" + username + "/" + biz_name + "/" + stamp

    print(content)

    img = qrcode.make(content)
    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)
    return send_file(buf, mimetype='image/jpeg')


@blueprint.route('/stamp/<string:username>/<string:biz_name>/<string:encrypted_date>', methods=['GET', 'POST'])
def api_apply_stamp(username, biz_name, encrypted_date):
    """ Business stamp an user
    ---
    """

    business = DB_Business.objects(username=username, safe_name=biz_name).first()

    if not business:
        return get_response_error_formatted(404, {'error_msg': "Business not found"})

    stamp = business.decode_stamp(encrypted_date)

    ret = {
        'result': "OK",
        'stamp_age_sec': stamp,
        'business': business.serialize(),
    }

    if stamp > 300:
        ret['result'] = "EXPIRED STAMP"

        ret.update({'error_msg': "Stamp expired and is GONE"})
        return get_response_error_formatted(410, ret)


    # Find user if there is an user

    # Increment the stamps amount

    #

    return get_response_formatted(ret)

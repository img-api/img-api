import requests
from api import api_key_or_login_required, get_response_formatted
from api.ai_services import blueprint
from api.company.models import DB_Company
from api.print_helper import *
from api.query_helper import build_query_from_request
from flask import request


@blueprint.route('/process/emails', methods=['GET', 'POST'])
#@api_key_or_login_required
def api_users_generate_emails():
    ret = {}
    return get_response_formatted(ret)


@blueprint.route('/ai_callback', methods=['GET', 'POST'])
#@api_key_or_login_required
def api_send_emails_callback_ai_summary():
    json = request.json

    ret = {}
    return get_response_formatted(ret)

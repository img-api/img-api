import socket
from datetime import datetime

import mistune
from api import get_response_formatted
from api.config import get_config_value, get_host_name
from api.test import blueprint
from api.user.models import User
from api.user.routes import send_email_user
from flask import Response, json, request
from flask_login import current_user


@blueprint.route('/', methods=['GET'])
def api_test_hello_world():
    """Returns a hello world for testing the API endpoint. A developer can call this to check that they can perform API calls.
    ---
    tags:
      - test
    schemes: ['http', 'https']
    deprecated: false
    definitions:
      hello_world:
        type: object
    responses:
      200:
        description: Returns a valid json with the msg hello world
        schema:
          id: hello world test
          type: object
          properties:
            msg:
                type: string
            status:
                type: string
            timestamp:
                type: string
            time:
                type: integer

    """
    print("hello world ")
    return get_response_formatted({'status': 'success', 'msg': 'hello world'})

@blueprint.route('/email', methods=['GET'])
def api_test_send_email_test():
    """
        Test that email is working
    """

    admin_user = User.objects(username="admin").first()

    subject = "EMAIL TEST: " + str(datetime.now())[:16] + " " + get_host_name()
    message = "# TESTING EMAIL \n"
    message += f"**{socket.gethostname()}**\n"
    message += str(datetime.now())

    html = mistune.html(message)

    res = send_email_user(admin_user, message, subject, html=html)

    if current_user.is_authenticated and current_user.is_admin:
        return get_response_formatted({'status': 'success', 'msg': res})

    return get_response_formatted({'status': 'success', 'msg': 'test'})

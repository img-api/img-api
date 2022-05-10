import os
import time
import datetime
from functools import wraps

from flask import json, jsonify, redirect, request, Response
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.exceptions import HTTPException

from api.user.models import User

from .api_redis import init_redis
from .print_helper import *

API_VERSION = "0.50pa"


def get_response_formatted(content, pretty=True):
    """ Returns a formatted response with the API version
        It cleans the input from private information.
        Admins will get the full API response """

    content['api'] = API_VERSION
    content['time'] = str(datetime.datetime.now())
    content['timestamp'] = int(time.time())

    if 'status' not in content:
        content['status'] = "success"

    content = json.dumps(content).encode('utf8')
    response = Response(content, mimetype='application/json')

    return response


def get_response_error_formatted(status, content, is_warning=False):
    """ Returns a formatted response with the API version

        HTTP Status ranges:
        1xx: Hold on
        2xx: Here you go
        3xx: Go away
        4xx: You failed up
        5xx: I failed up
    """

    content['api'] = API_VERSION

    content['status'] = 'error'
    content['error'] = status
    content['time'] = str(datetime.datetime.now())
    content['timestamp'] = int(time.time())

    response = Response(json.dumps(content, sort_keys=True, indent=4), status=status, mimetype='application/json')

    return response


def api_key_or_login_required(func):
    """
    Decorator for views that checks that the api call is in there, redirecting
    to the log-in page if necessary.

    The user might be logged in

    This function accepts several types of inputs

    # 1. API Key, it is a token that is encripted.
    #    It contains the user ID as 'id'
    #
    # 2. The user might be logged in, so we check if the login system from flask has the user registered

    """

    @wraps(func)
    def decorated_view(*args, **kwargs):
        user = None

        try:
            if current_user.is_authenticated and current_user.active:
                return func(*args, **kwargs)

        # A function might use Abort to exit, this will generate a
        # HTTPException but we want to return our API exceptions in JSON
        # Therefore we catch the exception and dump the description using our standard error response

        except HTTPException as errh:
            if 'error_msg' in errh.description:
                return get_response_error_formatted(errh.code, errh.description)

            return get_response_error_formatted(errh.code, {'error_msg': errh.description})

        except Exception as err:
            print(err, " CRASH ON USER. " + str(err))
            return get_response_error_formatted(400, {'error_msg': str(err)})

        token = request.args.get("key")
        if not token:
            if 'key' in request.form:
                token = request.form["key"]

        if not token:
            return get_response_error_formatted(401, {'error_msg': "No token or user found", "no_std": True})

        user = User.verify_auth_token(token)
        if isinstance(user, User) and user.active:
            print("\n------------ API LOGIN --------------")

            # The user might be already logged in
            if hasattr(current_user, "username"):
                # We logout the user if the key belongs to a different user.
                if current_user.username != user.username:
                    logout_user()

            # We login this user normally
            login_user(user, remember=True)

            ret = func(*args, **kwargs)
            logout_user()
            return ret

        return get_response_error_formatted(401, {'error_msg': "User Unauthorized, check token with admin"})

    return decorated_view


def api_key_login_or_anonymous(func):
    """
    Decorator for views that might want to login with an api key
    """

    @wraps(func)
    def decorated_view(*args, **kwargs):
        token = request.args.get("key")
        if not token:
            if 'key' in request.form:
                token = request.form["key"]

        if not token:
            return func(*args, **kwargs)

        user = User.verify_auth_token(token)
        if isinstance(user, User) and user.active:
            if hasattr(current_user, "username"):
                # Relogin the user if the key belongs to a different one
                if current_user.username != user.username:
                    logout_user()
                    login_user(user, remember=True)

            else:
                login_user(user, remember=True)

        return func(*args, **kwargs)

    return decorated_view

def configure_media_folder(app):
    """ Gets the media folder path from the environment or uses a local one inside the application """
    from api.tools import ensure_dir

    media_path = os.environ.get("IMGAPI_MEDIA_PATH", "")

    # The media folder SHOULD not be inside the application folder.
    if not media_path:
        media_path = app.root_path + "/MEDIA_FILES/"

        print("!-------------------------------------------------------------!")
        print("  WARNING MEDIA PATH IS NOT BEING DEFINED ")
        print("  PATH: " + media_path)
        print("!-------------------------------------------------------------!")

    app.config['MEDIA_PATH'] = media_path
    ensure_dir(media_path)


def register_api_blueprints(app):
    """ Loads all the modules for the API """
    from importlib import import_module

    print_b(" API BLUE PRINTS ")
    for module_name in (
            'user',
            'jobs',
            'admin',
            'media',
            'hello_world',
    ):
        module = import_module('api.{}.routes'.format(module_name))
        app.register_blueprint(module.blueprint)

        print(" Registering API " + str(module_name))

    configure_media_folder(app)
    init_redis(app)

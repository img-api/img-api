import os
import time
from datetime import datetime
from functools import wraps

import werkzeug
from flask import Response, json, jsonify, redirect, request
from flask_caching import Cache
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.exceptions import HTTPException

from api.query_helper import mongo_to_dict_helper
from api.user.models import User, user_loader

from .api_redis import init_redis
from .print_helper import *

API_VERSION = "0.50pa"

cache = Cache(config={'CACHE_TYPE': 'SimpleCache'})
api_ignore_list = ['tracking']


def api_clean_recursive(content, output):
    """ Cleans a dictionary of keys which are private.
        The only private key allowed is _id """

    if not content:
        return None

    is_admin = False
    if hasattr(current_user, "is_admin") and current_user.is_admin:
        is_admin = True

    if isinstance(content, str):
        output = content
        return output

    for key in content:
        value = content[key]
        if value == None:
            # print_r(key + ' is Empty')
            output[key] = ""
            continue

        if not is_admin and key in api_ignore_list:
            continue

        if not key:
            # print_h1(" FAIL KEY ")
            continue

        if key == "_id":
            if "$oid" in value:
                output["id"] = value["$oid"]

            # Helper to remove old IDs, we will find them and destroy them.
            output[key] = value
            continue

        if key[0] == "_":
            # print_r(key + '->' + value)
            continue

        if isinstance(value, dict):
            output[key] = api_clean_recursive(value, {})
        elif isinstance(value, str):
            # print_g(key + '->' + value)
            output[key] = value
            continue
        elif hasattr(value, "__iter__"):
            # print_b(" Found array " + key)
            output[key] = []
            for items in value:
                if isinstance(items, dict):
                    try:
                        clean = api_clean_recursive(items, {})
                        output[key].append(clean)
                    except Exception as e:
                        print_exception(e, "CRASH")
                        pass
                else:
                    output[key].append(items)

        else:
            output[key] = value

    return output


def api_clean(content):
    """ Cleans a dictionary of keys which are private. Also converts MONGO objects back to a dict that can be converted into json """
    from flask import json

    try:
        input = json.loads(json.dumps(content))
    except Exception as err:
        input = json.loads(json.dumps(content, default=lambda o: mongo_to_dict_helper(o)))

    output = api_clean_recursive(input, {})
    if not output:
        output = {'api': ""}

    return output


def get_response_formatted(input, pretty=True):
    """ Returns a formatted response with the API version
        It cleans the input from private information.
        Admins will get the full API response """

    content = api_clean(input)

    content['api'] = API_VERSION
    content['time'] = str(datetime.now())
    content['timestamp'] = int(time.time())

    if 'status' not in content:
        content['status'] = "success"

    if current_user.is_authenticated:
        content['current_user'] = current_user.username
    else:
        content['is_anon'] = True

    if pretty:
        content = json.dumps(content, sort_keys=True, indent=4)
    else:
        content = json.dumps(content)

    response = Response(content.encode('utf8'), mimetype='application/json')

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
    content['time'] = str(datetime.now())
    content['timestamp'] = int(time.time())

    if current_user.is_authenticated:
        content['current_user'] = current_user.username
    else:
        content['is_anon'] = True

    response = Response(json.dumps(content, sort_keys=True, indent=4), status=status, mimetype='application/json')

    return response


def api_get_token_from_request():
    token = request.args.get("key")
    if token:
        return token

    try:
        if request.form and 'key' in request.form:
            return request.form["key"]

        if 'Content-Type' in request.headers:
            if request.headers['Content-Type'] != 'application/json':
                print_r("WRONG CONTENT TYPE" + request.headers['Content-Type'])
                return None

            try:
                if hasattr(request, 'json') and request.json and 'key' in request.json:
                    return request.json["key"]
            except Exception as e:
                # The JSON parser crashes here in some calls, just ignore it.
                pass

        if 'HTTP_KEY' in request.headers:
            return request.headers['HTTP_KEY']

        # Last option. I don't really understand why is it not mapped to headers, but seems to work like this :?
        token = request.headers.environ.get('HTTP_KEY')

    except Exception as e:
        print_exception(e, "CRASH")

    return token


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
            token = api_get_token_from_request()

            # Check if the user has a token and we let the user to swap identities in case it is not the same user.
            if not token:
                if current_user.is_authenticated and current_user.active:
                    return func(*args, **kwargs)

                return get_response_error_formatted(401, {
                    'error_msg': "No user found, please login or create an account.",
                    "no_std": True
                })

            user = User.verify_auth_token(token)
            if isinstance(user, User) and user.active:
                print("\n------------ API LOGIN --------------")

                # The user might be already logged in
                if current_user.is_authenticated:
                    # We logout the user if the key belongs to a different user.
                    if current_user.username != user.username:
                        logout_user()

                # We login this user normally
                login_user(user, remember=True)

                ret = func(*args, **kwargs)
                logout_user()
                return ret

        except HTTPException as errh:
            # A function might use Abort to exit, this will generate a
            # HTTPException but we want to return our API exceptions in JSON
            # Therefore we catch the exception and dump the description using our standard error response

            if 'error_msg' in errh.description:
                return get_response_error_formatted(errh.code, errh.description)

            return get_response_error_formatted(errh.code, {'error_msg': errh.description})

        except Exception as err:
            print(err, " CRASH ON USER. " + str(err))
            return get_response_error_formatted(400, {'error_msg': str(err)})

        return get_response_error_formatted(401, {'error_msg': "User Unauthorized, check token with admin"})

    return decorated_view


def api_key_login_or_anonymous(func):
    """
    Decorator for views that might want to login with an api key
    """

    @wraps(func)
    def decorated_view(*args, **kwargs):

        try:
            token = api_get_token_from_request()
            if not token:
                return func(*args, **kwargs)

            user = User.verify_auth_token(token)
            if isinstance(user, User) and user.active:
                if current_user.is_authenticated:
                    # Relogin the user if the key belongs to a different one
                    if current_user.username != user.username:
                        logout_user()
                        login_user(user, remember=True)

                else:
                    login_user(user, remember=True)

            return func(*args, **kwargs)

        except HTTPException as errh:
            # A function might use Abort to exit, this will generate a
            # HTTPException but we want to return our API exceptions in JSON
            # Therefore we catch the exception and dump the description using our standard error response
            print_exception(errh, "ABORT")

            if 'error_msg' in errh.description:
                return get_response_error_formatted(errh.code, errh.description)

            return get_response_error_formatted(errh.code, {'error_msg': errh.description})

        except Exception as err:
            print(err, " CRASH ON USER. " + str(err))
            return get_response_error_formatted(400, {'error_msg': str(err)})

    return decorated_view


def configure_media_folder(app):
    """ Gets the media folder path from the environment or uses a local one inside the application """
    from api.tools import ensure_dir

    media_path = os.environ.get("IMGAPI_MEDIA_PATH", "")

    # The media folder SHOULD not be inside the application folder.
    if not media_path:
        media_path = app.root_path + "/DATA/MEDIA_FILES/"

        print("!-------------------------------------------------------------!")
        print("  WARNING MEDIA PATH IS NOT BEING DEFINED ")
        print("  PATH: " + media_path)
        print("!-------------------------------------------------------------!")

    app.config['MEDIA_PATH'] = media_path
    ensure_dir(media_path)


def handle_bad_request_with_html(e):
    import traceback

    from app.api_v1 import get_response_error_formatted

    traceback.print_tb(e.__traceback__)
    print(e.description)
    print(request.base_url)
    print_alert("BAD REQUEST EXCEPTION  [%s] [%d]" % (type(e), e.code))

    json = False
    try:
        if request.args.get('format') == 'html':
            json = False
        elif 'Content-Type' in request.headers and request.headers['Content-Type'] == 'application/json':
            json = True
        elif request.path.startswith("/api_v1/"):
            json = True

        if json:
            return get_response_error_formatted(e.code, {
                'error_msg': e.description,
                'no_std': True,
            })
    except Exception as e:
        print_exception(e, "UNAUTHORIZED HANDLER")

    return render_template('errors/page_{}.html'.format(e.code)), e.code


def register_api_blueprints(app):
    """ Loads all the modules for the API """
    from importlib import import_module

    from api.news import configure_news_media_folder
    global cache

    #print_b(" API BLUE PRINTS ")
    for module_name in (
            'user',
            'news',
            'jobs',
            'admin',
            'media',
            'actors',
            'ticker',
            'events',
            'people',
            'content',
            'company',
            'galleries',
            'hello_world',
    ):
        module = import_module('api.{}.routes'.format(module_name))
        app.register_blueprint(module.blueprint)

        #print(" Registering API " + str(module_name))

    configure_media_folder(app)
    configure_news_media_folder(app)
    init_redis(app)

    # Cache
    cache.init_app(app)

import os
import traceback

import mongoengine
import werkzeug
from flask import Flask, json
from flask_cors import CORS
from flask_login import LoginManager

app = Flask(__name__)

if os.environ.get('IMGAPI_SETTINGS', False):
    app.config.from_envvar('IMGAPI_SETTINGS')

MONGODB_SETTINGS = {'host': 'mongodb://localhost/demo', 'port': 27017}

app.config.update(DEBUG=True, MONGODB_SETTINGS=MONGODB_SETTINGS)

# Path to the configuration file
config_path = os.environ.get('IMGAPI_CONFIG', os.path.expanduser('~/.imgapi.json'))

# Check if the file exists
if os.path.exists(config_path):
    with open(config_path) as config_file:
        config_data = json.load(config_file)
        app.config.update(config_data)
else:
    print("Config file not found")

# Tests (and one-off tools) can point at another database without a config file
if os.environ.get('IMGAPI_MONGODB_HOST'):
    app.config['MONGODB_SETTINGS'] = {'host': os.environ['IMGAPI_MONGODB_HOST']}

# The secret key signs every login token: whoever knows it can log in as anyone.
# It comes from the config file (or IMGAPI_SECRET_KEY) and must never be one
# that has been published. Generate one with:
#   python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
if os.environ.get('IMGAPI_SECRET_KEY'):
    app.config['SECRET_KEY'] = os.environ['IMGAPI_SECRET_KEY']

# sha256 of keys that were committed to the public repo
PUBLISHED_KEYS = {
    "d672fa89866d0f90e60d8f5bd193fa2744c6a6732476a7da36a46c5d7c932324",
}


def check_secret_key(key):
    import hashlib
    if not key or len(key) < 32 or key.startswith("CHANGE-ME"):
        return "SECRET_KEY is missing or too short (32+ characters)"
    if hashlib.sha256(key.encode()).hexdigest() in PUBLISHED_KEYS:
        return "SECRET_KEY is the one published in the git repo"
    return None


secret_problem = check_secret_key(app.config.get('SECRET_KEY'))
if secret_problem:
    raise RuntimeError(f"{secret_problem}. Set a new one in {config_path} (see imgapi_launcher.py).")


class MongoEngine:
    """ Minimal replacement for flask_mongoengine (unmaintained, no Flask 3).
        Models use db.StringField, db.DynamicDocument... which map to mongoengine. """

    def __getattr__(self, name):
        return getattr(mongoengine, name)

    def init_app(self, app):
        settings = dict(app.config['MONGODB_SETTINGS'])
        settings.setdefault('uuidRepresentation', 'pythonLegacy')  # same as before
        mongoengine.connect(**settings)


# Database initialization
db = MongoEngine()
db.init_app(app)

# Login manager to handle users
login_manager = LoginManager()
login_manager.init_app(app)

from api import register_api_blueprints
# Blue prints section
from app import register_app_blueprints

register_api_blueprints(app)
register_app_blueprints(app)


# CORS: media files can be embedded by any site (no cookies). The rest of the
# API only answers our own frontends from a browser, with cookies: any other
# site's scripts can't read responses or act with a visitor's session.
# Extra origins: "CORS_ORIGINS": [...] in the config file.
CORS_ORIGINS = app.config.get('CORS_ORIGINS') or [
    "https://img-api.com", "https://www.img-api.com", "https://dev.img-api.com",
]
CORS(app, resources={
    r"/api/media/get/*": {"origins": "*", "supports_credentials": False},
    r"/*": {"origins": CORS_ORIGINS, "supports_credentials": True,
            "allow_headers": ["Content-Type", "Authorization"]},
})


def handle_bad_request(e):

    from api import get_response_error_formatted
    from api.print_helper import print_alert

    traceback.print_tb(e.__traceback__)
    print_alert("BAD REQUEST EXCEPTION  [%s] [%d]" % (type(e), e.code))

    return get_response_error_formatted(e.code, {
        'error_msg': e.description,
        'no_std': True,
    })


app.register_error_handler(werkzeug.exceptions.NotFound, handle_bad_request)
app.register_error_handler(werkzeug.exceptions.BadRequest, handle_bad_request)

app.register_error_handler(400, handle_bad_request)  # Bad request
app.register_error_handler(404, handle_bad_request)  # URL missing
app.register_error_handler(500, handle_bad_request)  # Internal server error

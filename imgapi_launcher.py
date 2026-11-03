import os
import traceback

import mongoengine
import werkzeug
from flask import Flask, json
from flask_cors import CORS
from flask_login import LoginManager

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

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

# The secret key comes from the config file (or IMGAPI_SECRET_KEY).
# The fallback is only good for local development.
if os.environ.get('IMGAPI_SECRET_KEY'):
    app.config['SECRET_KEY'] = os.environ['IMGAPI_SECRET_KEY']
if not app.config.get('SECRET_KEY'):
    print("WARNING: SECRET_KEY not configured, using the insecure development key")
    app.config['SECRET_KEY'] = "dev-only-insecure-secret-key"


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


@app.after_request
def after_request(response):
    """ We are a public API, we return that we enable everything (Overrides Cors) """

    # Using CORS for this part of the credentials
    #origin = request.environ.get('HTTP_ORIGIN', '*')
    #response.headers.add('Access-Control-Allow-Origin', origin)

    response.headers.add('Access-Control-Allow-Credentials', 'true')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    return response


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

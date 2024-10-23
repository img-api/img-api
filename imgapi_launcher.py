import os
import traceback
from importlib import import_module

import werkzeug
from flasgger import LazyJSONEncoder, LazyString, Swagger, swag_from
from flask import Flask, json, jsonify, request
from flask_cors import CORS
from flask_login import LoginManager, current_user
from flask_mongoengine import MongoEngine, MongoEngineSessionInterface

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Enable CORS on the entire application

if os.environ.get('IMGAPI_SETTINGS', False):
    app.config.from_envvar('IMGAPI_SETTINGS')

MONGODB_SETTINGS = {'host': 'mongodb://localhost/demo', 'port': 27017}

app.config.update(DEBUG=True, MONGODB_SETTINGS=MONGODB_SETTINGS, SECRET_KEY="mysecret_key_loaded_from_the_system")

# Path to the configuration file
config_path = os.path.expanduser('~/.imgapi.json')

# Check if the file exists
if os.path.exists(config_path):
    with open(config_path) as config_file:
        config_data = json.load(config_file)
        app.config.update(config_data)
else:
    print("Config file not found")

# Database initialization

db = MongoEngine()
db.init_app(app)

# Login manager to handle users

login_manager = LoginManager()
login_manager.init_app(app)

# Swagger and documentation

app.json_encoder = LazyJSONEncoder  # Required by swagger
"""
app.config['SWAGGER'] = {'title': 'IMG API', 'DEFAULT_MODEL_DEPTH': -1}

swagger_template = dict(
    info={
        'title':
        LazyString(lambda: 'IMG-API API document'),
        'version':
        LazyString(lambda: '0.1'),
        'description':
        LazyString(
            lambda:
            'API Description to upload, convert, operate and download images and media  <style>.models {display: none !important}</style>'
        ),
        "basePath":
        "/docs",  # base bash for blueprint registration
    },
    host=LazyString(lambda: request.host))

swagger_config = {
    "headers": [],
    "specs": [{
        "endpoint": 'imgapi_doc_v1',
        "route": '/imgapi_doc_v1.json',
        "rule_filter": lambda rule: True,
        "model_filter": lambda tag: True,
    }],
    "static_url_path":
    "/flasgger_static",
    "swagger_ui":
    True,
    "specs_route":
    "/apidocs/"
}

template = dict(swaggerUiPrefix=LazyString(lambda: request.environ.get('HTTP_X_SCRIPT_NAME', '')))
swagger = Swagger(app, template=swagger_template, config=swagger_config)
"""

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

import os
from flask import Flask, jsonify, request

from flasgger import Swagger, LazyString, LazyJSONEncoder
from flasgger import swag_from
from importlib import import_module

from flask_login import current_user, LoginManager
from flask_mongoengine import MongoEngine, MongoEngineSessionInterface

app = Flask(__name__)

MONGODB_SETTINGS = {'host': 'localhost', 'port': 27017}

app.config.update(DEBUG=True, MONGODB_SETTINGS=MONGODB_SETTINGS, SECRET_KEY="mysecret_key_loaded_from_the_system")

# Database initialization

db = MongoEngine()
db.init_app(app)

# Login manager to handle users

login_manager = LoginManager()
login_manager.init_app(app)

# Swagger and documentation

app.json_encoder = LazyJSONEncoder  # Required by swagger
app.config['SWAGGER'] = {'title': 'IMG API', 'DEFAULT_MODEL_DEPTH': -1}

swagger_template = dict(
    info={
        'title': LazyString(lambda: 'IMG-API API document'),
        'version': LazyString(lambda: '0.1'),
        'description': LazyString(lambda: 'API Description to upload, convert, operate and download images and media'),
        "basePath": "/docs",  # base bash for blueprint registration
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

# Blue prints section
from app import register_app_blueprints
from api import register_api_blueprints

register_api_blueprints(app)
register_app_blueprints(app)


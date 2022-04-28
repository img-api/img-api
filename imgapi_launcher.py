from flask import Flask, jsonify, request

from flasgger import Swagger, LazyString, LazyJSONEncoder
from flasgger import swag_from
from importlib import import_module

app = Flask(__name__)
app.json_encoder = LazyJSONEncoder
app.config['SWAGGER'] = {
    'title': 'IMG API'
}

swagger_template = dict(info={
    'title': LazyString(lambda: 'IMG-API API document'),
    'version': LazyString(lambda: '0.1'),
    'description': LazyString(lambda: 'API Description to upload, convert, operate and download images'),
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
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/"
}

template = dict(swaggerUiPrefix=LazyString(lambda : request.environ.get('HTTP_X_SCRIPT_NAME', '')))

swagger = Swagger(app, template=swagger_template, config=swagger_config)

def register_api_blueprints(app):
    print(" API BLUE PRINTS ")
    for module_name in (
            'admin',
            'hello_world',
    ):
        module = import_module('api.{}.routes'.format(module_name))
        app.register_blueprint(module.blueprint)

        print(" Registering API " + str(module_name))


def register_app_blueprints(app):
    print(" APP BLUE PRINTS ")
    for module_name in (
            'root',
            'landing',
    ):
        module = import_module('app.{}.routes'.format(module_name))
        app.register_blueprint(module.blueprint)

        print(" Registering API " + str(module_name))


# Our application is composed by the VIEW that facilities admin, access to the documentation and APIs
register_api_blueprints(app)
register_app_blueprints(app)


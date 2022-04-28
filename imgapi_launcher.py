from flask import Flask, jsonify, request
from flask_swagger import swagger

from flasgger import Swagger, LazyString, LazyJSONEncoder
from flasgger import swag_from

app = Flask(__name__)
app.json_encoder = LazyJSONEncoder

swagger_template = dict(info={
    'title': LazyString(lambda: 'IMG-API API document'),
    'version': LazyString(lambda: '0.1'),
    'description': LazyString(lambda: 'API Description to upload, convert and download images'),
},
                        host=LazyString(lambda: request.host))

swagger_config = {
    "headers": [],
    "specs": [{
        "endpoint": 'hello_world',
        "route": '/hello_world.json',
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

swagger = Swagger(app, template=swagger_template, config=swagger_config)

@app.route("/")
def home():
    return "Hello, World"


@app.route("/spec")
def spec():
    swag = swagger(app)
    swag['info']['version'] = "1.0"
    swag['info']['title'] = "IMG API"
    return jsonify(swag)
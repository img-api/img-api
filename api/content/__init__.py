from flask import Blueprint
from flask_cors import CORS

blueprint = Blueprint('api_content_blueprint',
                      __name__,
                      url_prefix='/api/content',
                      template_folder='templates',
                      static_folder='static')

CORS(blueprint)
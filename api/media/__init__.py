from flask import Blueprint
from flask_cors import CORS

blueprint = Blueprint('api_upload_blueprint',
                      __name__,
                      url_prefix='/api/media',
                      template_folder='templates',
                      static_folder='static')

CORS(blueprint)
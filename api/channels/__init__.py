from flask import Blueprint
from flask_cors import CORS

blueprint = Blueprint('api_channels_blueprint',
                      __name__,
                      url_prefix='/api/channels',
                      template_folder='templates',
                      static_folder='static')

CORS(blueprint)

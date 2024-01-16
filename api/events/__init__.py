from flask import Blueprint
from flask_cors import CORS

blueprint = Blueprint('api_events_blueprint',
                      __name__,
                      url_prefix='/api/events',
                      template_folder='templates',
                      static_folder='static')

CORS(blueprint)
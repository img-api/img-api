import time
import datetime

from flask import Blueprint
from flask_cors import CORS

blueprint = Blueprint('api_actors_blueprint',
                      __name__,
                      url_prefix='/api/actors',
                      template_folder='templates',
                      static_folder='static')

CORS(blueprint)
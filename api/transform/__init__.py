import time
import datetime

from flask import Blueprint

blueprint = Blueprint('api_transform_blueprint',
                      __name__,
                      url_prefix='/api/transform',
                      template_folder='templates',
                      static_folder='static')

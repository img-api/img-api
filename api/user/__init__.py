import time
import datetime

from flask import Blueprint

blueprint = Blueprint('api_user_blueprint',
                      __name__,
                      url_prefix='/api/user',
                      template_folder='templates',
                      static_folder='static')

import time
import datetime

from flask import Blueprint

blueprint = Blueprint('app_user_setup_blueprint',
                      __name__,
                      url_prefix='/setup',
                      template_folder='templates',
                      static_folder='static')

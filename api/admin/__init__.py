import time
import datetime

from flask import Blueprint

blueprint = Blueprint('api_admin_blueprint',
                      __name__,
                      url_prefix='/api/admin',
                      template_folder='templates',
                      static_folder='static')

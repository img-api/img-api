import time
import datetime

from flask import Blueprint

blueprint = Blueprint('api_business_blueprint',
                      __name__,
                      url_prefix='/api/biz',
                      template_folder='templates',
                      static_folder='static')

import time
import datetime

from flask import Blueprint

blueprint = Blueprint('api_category_blueprint',
                      __name__,
                      url_prefix='/api/category',
                      template_folder='templates',
                      static_folder='static')

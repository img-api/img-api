import time
import datetime

from flask import Blueprint

blueprint = Blueprint('api_content_blueprint',
                      __name__,
                      url_prefix='/api/content',
                      template_folder='templates',
                      static_folder='static')

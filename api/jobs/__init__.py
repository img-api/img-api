import time
import datetime

from flask import Blueprint

blueprint = Blueprint('api_jobs_blueprint',
                      __name__,
                      url_prefix='/api/jobs',
                      template_folder='templates',
                      static_folder='static')

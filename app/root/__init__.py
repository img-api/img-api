import time
import datetime

from flask import Blueprint

blueprint = Blueprint(
    'app_root_blueprint',
    __name__,
    url_prefix='/',
    template_folder='templates',
    static_folder='static'
)

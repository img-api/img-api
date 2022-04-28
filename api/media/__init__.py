import time
import datetime

from flask import Blueprint

blueprint = Blueprint(
    'api_upload_blueprint',
    __name__,
    url_prefix='/api/media',
    template_folder='templates',
    static_folder='static'
)

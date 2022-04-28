import time
import datetime

from flask import Blueprint

blueprint = Blueprint(
    'api_upload_blueprint',
    __name__,
    url_prefix='/api/image',
    template_folder='templates',
    static_folder='static'
)

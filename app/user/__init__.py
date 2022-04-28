import time
import datetime

from flask import Blueprint

blueprint = Blueprint(
    'app_user_media_blueprint',
    __name__,
    url_prefix='/u',
    template_folder='templates',
    static_folder='static'
)

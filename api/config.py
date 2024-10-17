import os
from datetime import datetime

from flask import current_app as app


def get_config_value(key, default_value=None):
    try:
        with app.app_context():
            return app.config[key]
    except:
        pass

    return default_value

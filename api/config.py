import os
import socket
from datetime import datetime

from flask import current_app as app


def get_config_value(key, default_value=None):
    try:
        with app.app_context():
            return app.config[key]
    except:
        pass

    return default_value


def get_port():
    try:
        import os
        port = os.environ['FLASK_PORT']
        if (port):
            return port

    except Exception as e:
        return None

    return None


def get_host_name():
    try:
        with app.app_context():
            if app.config['PUBLIC_HOST']:
                return app.config['PUBLIC_HOST']

    except Exception as err:
        print("! TODO: Find why this application can read the host " + str(err))

    port = get_port()
    if (port):
        return socket.gethostname() + ":" + port

    # We remap the main machine to evam.software
    if (socket.gethostname() == "gputop"):
        return "tothemoon.life"

    return socket.gethostname()

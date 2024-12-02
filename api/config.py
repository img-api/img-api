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


def get_api_entry():
    """
        Returns different from production or development
        If the user defines FLASK_API_DEV in the environment they will get that in development
        Otherwise it will return the FLASK_API_PROD or default
    """
    try:
        if os.environ.get('FLASK_ENV', None) == "development":
            return os.environ.get('FLASK_API_DEV', "http://dev.tothemoon.life/api")

        return os.environ.get('FLASK_API_PROD', "https://headingtomars.com/api")

    except Exception as err:
        print("! TODO: Find why this application can read the host " + str(err))

    return "https://tothemoon.life/api"


def get_api_AI_default_service():
    return "https://lachati.com/api_v1"


def get_api_AI_service():
    """
        If the user defines FLASK_API_AI_DEV
    """
    default_service = get_api_AI_default_service() + "/upload-json"
    try:
        if os.environ.get('FLASK_ENV', None) == "development":
            if os.environ.get('FLASK_API_AI_DEV'):
                return os.environ.get('FLASK_API_AI_DEV')

        if os.environ.get('FLASK_API_AI_PROD'):
            return os.environ.get('FLASK_API_AI_PROD')

    except Exception as err:
        print("! TODO: Find why this application can read the host " + str(err))

    return default_service

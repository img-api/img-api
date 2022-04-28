import time
import datetime

from flask import json, jsonify, redirect, request, Response

API_VERSION = "0.50pa"

def get_response_formatted(content, pretty=True):
    """ Returns a formatted response with the API version
        It cleans the input from private information.
        Admins will get the full API response """

    content['api'] = API_VERSION
    content['time'] = str(datetime.datetime.now())
    content['timestamp'] = int(time.time())

    content = json.dumps(content).encode('utf8')
    response = Response(content, mimetype='application/json')
    return response


def get_response_error_formatted(status, content, is_warning=False):
    """ Returns a formatted response with the API version

        HTTP Status ranges:
        1xx: Hold on
        2xx: Here you go
        3xx: Go away
        4xx: You fucked up
        5xx: I fucked up
    """

    content['api'] = API_VERSION

    content['status'] = 'error'
    content['error'] = status
    content['time'] = str(datetime.datetime.now())
    content['timestamp'] = int(time.time())

    return Response(json.dumps(content, sort_keys=True, indent=4), status=status, mimetype='application/json')
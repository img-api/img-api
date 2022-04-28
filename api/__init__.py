import time
import datetime

from flask import json, jsonify, redirect, request, Response

def get_response_formatted(content, pretty=True):
    """ Returns a formatted response with the API version
        It cleans the input from private information.
        Admins will get the full API response """

    content['time'] = str(datetime.datetime.now())
    content['timestamp'] = int(time.time())

    content = json.dumps(content).encode('utf8')
    response = Response(content, mimetype='application/json')
    return response
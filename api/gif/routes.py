import binascii
import io
import random
import re
import time
from datetime import datetime

import bcrypt
import qrcode
import requests
import validators
from api import (admin_login_required, api_key_login_or_anonymous,
                 api_key_or_login_required, cache,
                 get_response_error_formatted, get_response_formatted)
from api.gif import blueprint
from api.gif.models import DB_Gif
from api.print_helper import *
from api.query_helper import (build_query_from_request, mongo_to_dict_helper,
                              validate_and_convert_dates)
from api.tools.validators import get_validated_email
from flask import Response, abort, jsonify, redirect, request, send_file
from flask_login import current_user
from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q


@blueprint.route('/gif', methods=['GET', 'POST'])
def api_gif_get_from_request():
    """ """
    from io import BytesIO

    from .sentiment import get_gif_for_sentiment

    keywords = request.args.get("keywords", "SAD")

    raw_data, gif, format = get_gif_for_sentiment(keywords)

    raw = request.args.get("raw", None)

    if raw:
        ret = {"keywords": keywords, 'url': gif, 'raw': raw_data, 'format': format}
        return get_response_formatted(ret)

    response = requests.get(gif)
    if response.status_code != 200:
        return {"error": "Failed to download the gif"}, 500

    # Create a temporary file to store the gif data
    gif_data = BytesIO(response.content)
    if format == "mp4":
        return send_file(gif_data, mimetype='video/mp4', as_attachment=False, download_name='sentiment.mp4')

    return send_file(gif_data, mimetype='image/gif', as_attachment=False, download_name='sentiment.gif')

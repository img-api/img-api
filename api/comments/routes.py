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
from api.news import blueprint
from api.news.models import DB_News
from api.print_helper import *
from api.query_helper import (build_query_from_request, mongo_to_dict_helper,
                              validate_and_convert_dates)
from api.tools.validators import get_validated_email
from flask import Response, abort, jsonify, redirect, request, send_file
from flask_login import current_user
from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q

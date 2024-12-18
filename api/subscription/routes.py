import io
import socket
from datetime import datetime

import requests
from api import cache, get_response_error_formatted, get_response_formatted
from api.company.models import DB_Company, DB_CompanyPrompt
from api.config import get_api_AI_service, get_api_entry
from api.print_helper import *
from api.query_helper import (build_query_from_request, get_timestamp_verbose,
                              is_mongo_id)
from api.subscription import blueprint
from flask import request, send_file
from mongoengine.queryset.visitor import Q

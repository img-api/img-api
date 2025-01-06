import base64
import time
import urllib.parse
from datetime import datetime

import rsa
from api.print_helper import *
from api.query_helper import *
from imgapi_launcher import db
from mongoengine import *

class DB_Subscription(db.DynamicDocument):
    meta = {
        'strict': False,
    }

    username = db.StringField()

    last_update_date = db.DateTimeField()
    last_update_date = db.DateTimeField()

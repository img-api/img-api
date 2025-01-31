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


class DB_Subscription_alert(db.DynamicDocument):
    meta = {
        'strict': False,
    }

    username = db.StringField()
    news_id = db.StringField()

    last_update_date = db.DateTimeField()


class DB_Email_Subscription(db.DynamicDocument):
    meta = {
        'strict': False,
    }

    email = db.StringField()
    username = db.StringField()

    last_update_date = db.DateTimeField()
    is_validated = db.BooleanField(default=False)

    is_subscribed_marketing = db.BooleanField(default=True)
    is_subscribed_email = db.BooleanField(default=True)
    is_subscribed_newsletter = db.BooleanField(default=True)

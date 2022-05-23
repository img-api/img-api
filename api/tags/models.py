import os
import time
import datetime

from mongoengine import *

from imgapi_launcher import db

from flask import current_app
from flask_login import current_user


class DB_Tags(db.DynamicDocument):
    meta = {
        'strict': False,
    }

    tag = db.StringField()
    creation_date = db.DateTimeField()
    related = db.ListField(db.StringField())


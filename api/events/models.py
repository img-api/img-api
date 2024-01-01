import os
import time
import datetime

from mongoengine import *

from imgapi_launcher import db

from flask import current_app
from flask_login import current_user


class DB_Event(db.DynamicDocument):
    meta = {
        'strict': False,
    }

    name = db.StringField()
    creation_date = db.DateTimeField()
    end_date = db.DateTimeField()



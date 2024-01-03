import os
import time
from datetime import datetime

from mongoengine import *

from imgapi_launcher import db

from flask import current_app
from flask_login import current_user
from api.user.user_check import DB_UserCheck

from api.query_helper import get_value_type_helper

class DB_Event(DB_UserCheck, db.DynamicDocument):
    """ Class to create an event

    """
    meta = {
        'strict': False,
        "auto_create_index": True,
        "index_background": True,
    }

    title = db.StringField()
    gallery_id = db.StringField()

    end_date = db.DateTimeField()

    last_access_date = db.DateTimeField()

    progress = db.FloatField()      # Progress from 0 to 1
    priority = db.IntField()        # Position on the group list

    def save(self, *args, **kwargs):
        if not self.creation_date:
            self.creation_date = datetime.now()

        last_access_date = datetime.now()
        ret = super(DB_Event, self).save(*args, **kwargs)
        ret.reload()
        return ret

    def serialize(self):
        ret = mongo_to_dict_helper(self)
        return ret
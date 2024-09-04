import os
import time
import shutil
import bleach

from datetime import datetime

from mongoengine import *

from api.print_helper import *
from api.query_helper import *

from flask import current_app
from flask_login import UserMixin, current_user

from imgapi_launcher import db, login_manager
from api.query_helper import mongo_to_dict_helper

from api.user.user_check import DB_UserCheck


class DB_UserContent(DB_UserCheck, db.DynamicDocument):
    meta = {'strict': False, 'indexes': ['username', 'section']}

    last_access_date = db.DateTimeField()
    section = db.StringField()

    html = db.StringField(default="=== Click ME! ===")

    def save(self, *args, **kwargs):
        if not self.creation_date:
            self.creation_date = datetime.now()

        last_access_date = datetime.now()
        ret = super(DB_UserContent, self).save(*args, **kwargs)
        ret.reload()
        return ret

    def set_key_value(self, key, value):
        if not self.is_current_user():
            return False

        # My own fields that can be edited:
        if not key.startswith('my_') and key not in ["html"]:
            return False

        value = bleach.clean(value, tags=['a', 'b', 'i', 'u', 'em', 'strong', 'p'], attributes=[])
        if key == "html":
            self.update(**{key: value}, validate=False)
            self.reload()
            return True

        value = get_value_type_helper(self, key, value)
        if value != self[key]:
            self.update(**{key: value}, validate=False)
            self.reload()

        return True

    def serialize(self):
        """ Cleanup version of the media file so don't release confidential information """
        ret = mongo_to_dict_helper(self)

        return ret
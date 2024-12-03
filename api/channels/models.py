import base64
import os
import shutil
import time
import urllib.parse
from datetime import datetime

from api.print_helper import *
from api.query_helper import *
from flask_login import UserMixin, current_user
from imgapi_launcher import db, login_manager
from mongoengine import *


class DB_Channel(db.DynamicDocument):
    meta = {
        'strict': False,
    }

    creation_date = db.DateTimeField()
    last_update_date = db.DateTimeField()

    name = db.StringField()
    summary = db.StringField()

    def __init__(self, *args, **kwargs):
        super(DB_Channel, self).__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        if not self.creation_date:
            self.creation_date = datetime.now()

        ret = super(DB_Channel, self).save(*args, **kwargs)
        ret.reload()
        return ret

    def delete(self, *args, **kwargs):
        print(" DELETED Data ")
        return super(DB_Channel, self).delete(*args, **kwargs)

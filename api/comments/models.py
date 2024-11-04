import base64
import os
import shutil
import time
import urllib.parse
from datetime import datetime

import rsa
from api.galleries.models import DB_UserGalleries
from api.print_helper import *
from api.query_helper import *
from api.query_helper import mongo_to_dict_helper
from api.tools.signature_serializer import BadSignature, SignatureExpired
from api.tools.signature_serializer import \
    TimedJSONWebSignatureSerializer as Serializer
from api.user.user_check import DB_UserCheck
from flask import current_app
from flask_login import UserMixin, current_user
from imgapi_launcher import db, login_manager
from mongoengine import *


class DB_Comment(db.DynamicDocument):
    """ Comment article
    """
    meta = {
        'strict': False,
    }

    status = db.StringField()
    title = db.StringField()

    creation_date = db.DateTimeField()
    last_visited_date = db.DateTimeField()

    username = db.StringField()
    status = db.StringField()

    ref_id = db.StringField()
    parent_id = db.StringField()

    is_NSFW = db.BooleanField(default=False)
    is_ghosted = db.BooleanField(default=False)
    is_moderated = db.BooleanField(default=False)

    def __init__(self, *args, **kwargs):
        super(DB_Comment, self).__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        if not self.creation_date:
            self.creation_date = datetime.now()

        ret = super(DB_Comment, self).save(*args, **kwargs)
        return ret

    def delete(self, *args, **kwargs):
        print(" DELETED Comment Data ")
        return super(DB_Comment, self).delete(*args, **kwargs)


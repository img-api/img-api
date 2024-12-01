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


class DB_TenorGif(db.DynamicDocument):
    """ We store the documents that we download for third party websites so we can cache the API
    """
    meta = {
        'strict': False,
    }

    creation_date = db.DateTimeField()
    description = db.StringField()

    external_uuid = db.StringField()
    media_id = db.StringField()

    def __init__(self, *args, **kwargs):
        super(DB_TenorGif, self).__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        if not self.creation_date:
            self.creation_date = datetime.now()

        ret = super(DB_TenorGif, self).save(*args, **kwargs)
        return ret

    def delete(self, *args, **kwargs):
        return super(DB_TenorGif, self).delete(*args, **kwargs)

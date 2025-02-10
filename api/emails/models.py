import os
import rsa
import time
import base64
import shutil
from datetime import datetime

import urllib.parse

from mongoengine import *
from api.print_helper import *
from api.query_helper import *

from flask import current_app
from flask_login import UserMixin, current_user

from imgapi_launcher import db, login_manager
from api.query_helper import mongo_to_dict_helper

from api.tools.signature_serializer import TimedJSONWebSignatureSerializer as Serializer, BadSignature, SignatureExpired

from api.galleries.models import DB_UserGalleries
from api.user.user_check import DB_UserCheck


class DB_EmailStore(db.DynamicDocument):
    meta = {
        'strict': False,
    }

    last_update_date = db.DateTimeField()

    def save(self, *args, **kwargs):
        self.last_update_date = datetime.now()

        ret = super(DB_EmailStore, self).save(*args, **kwargs)
        return ret.reload()


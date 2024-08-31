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

class DB_DynamicNewsRawData(db.DynamicDocument):
    meta = {
        'strict': False,
    }

    creation_date = db.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.creation_date:
            self.creation_date = datetime.now()

        ret = super(DB_DynamicNewsRawData, self).save(*args, **kwargs)
        return ret.reload()


class DB_News(db.DynamicDocument):
    """ News is our class helper that downloads and indexes our news data

        It will save the images and files into disk so we can process them later.
        First iteration is just data in the database.
    """
    meta = {
        'strict': False,
    }

    status = db.StringField()
    creation_date = db.DateTimeField()
    last_visited_date = db.DateTimeField()

    link = db.StringField()
    thumbnail_url = db.StringField()

    news_type = db.StringField()
    publisher = db.StringField()

    ai_summary = db.StringField()

    external_uuid = db.StringField()

    # Tickers that are
    related_exchange_tickers = db.ListField(db.StringField(), default=list)

    # Source -  The source will define the processing backend. For example yfinance will fetch the URL
    #           and navigate until getting the full news source.
    source = db.StringField()

    # We store the raw data from the fetch so we can reprocess or extract extra info
    raw_data_id = db.StringField()

    def __init__(self, *args, **kwargs):
        super(DB_News, self).__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        if not self.creation_date:
            self.creation_date = datetime.now()

        ret = super(DB_News, self).save(*args, **kwargs)
        return ret

    def delete(self, *args, **kwargs):
        #abs_path = self.get_media_path() + self.file_path
        #if os.path.exists(abs_path):
        #    os.remove(abs_path)

        print(" DELETED News Data ")
        return super(DB_News, self).delete(*args, **kwargs)

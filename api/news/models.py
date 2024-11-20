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
    title = db.StringField()

    creation_date = db.DateTimeField()
    last_visited_date = db.DateTimeField()
    ai_upload_date = db.DateTimeField()

    link = db.StringField()
    thumbnail_url = db.StringField()

    news_type = db.StringField()
    publisher = db.StringField()

    articles = db.ListField(db.StringField(), default=list)

    experiment = db.StringField()

    ai_summary = db.StringField()

    external_uuid = db.StringField()
    force_reindex = db.BooleanField(default=False)

    # Tickers that are
    related_exchange_tickers = db.ListField(db.StringField(), default=list)

    # Source -  The source will define the processing backend. For example yfinance will fetch the URL
    #           and navigate until getting the full news source.
    source = db.StringField()

    # Storage where we cache the fetch
    raw_files_path = db.StringField()

    # We store the raw data from the fetch so we can reprocess or extract extra info
    raw_data_id = db.StringField()

    is_blocked = db.BooleanField(default=False)
    blocked_by = db.ListField(db.StringField(), default=list)

    languages = db.ListField(db.StringField(), default=list)

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

    def set_state(self, state_msg):
        """ Update a processing state """

        print_b(self.link + " " + self.status + " => " + state_msg)

        self.update(**{
            'force_reindex': False,
            'status': state_msg,
            'last_visited_date': datetime.now()
        },
                    validate=False)

        self.reload()
        return self

    def get_data_folder(self):
        from api.tools import ensure_dir

        path = current_app.config.get('DATA_NEWS_PATH', None)
        path += self.source + "/" + str(self.id) + "/"
        ensure_dir(path)

        return path


    def set_key_value(self, key, value):
        # Only for admin
        value = get_value_type_helper(self, key, value)

        update = {key: value}

        if update:
            self.update(**update, validate=False)

        return True

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
    source_title = db.StringField()

    creation_date = db.DateTimeField()
    last_visited_date = db.DateTimeField()
    ai_upload_date = db.DateTimeField()

    link = db.StringField()
    thumbnail_url = db.StringField()

    news_type = db.StringField()
    publisher = db.StringField()

    articles = db.ListField(db.StringField(), default=list)

    experiment = db.StringField()

    interest_score = db.IntField()
    sentiment_score = db.IntField()

    stock_price = db.FloatField()

    ai_summary = db.StringField()

    external_uuid = db.StringField()
    force_reindex = db.BooleanField(default=False)

    # Tickers that are
    related_exchange_tickers = db.ListField(db.StringField(), default=list)
    named_exchange_tickers = db.DynamicDocument()

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

    last_cache_date = db.DateTimeField()
    no_comments = db.IntField()

    def age_minutes(self, *args, **kwargs):
        age = (datetime.now() - self.creation_date).total_seconds() / 60
        return age

    def age_cache_minutes(self, *args, **kwargs):
        age = (datetime.now() - self.last_cache_date).total_seconds() / 60
        return age

    def precalculate_name_tickers(self):
        from api.company.models import DB_Company
        from api.ticker.tickers_helpers import standardize_ticker_format

        if len(self.named_exchange_tickers) == len(self.related_exchange_tickers):
            return None

        res = {}
        for ticker in self.related_exchange_tickers:
            ticker_cleanup = standardize_ticker_format(ticker)
            db_company = DB_Company.objects(exchange_tickers=ticker_cleanup).first()

            if db_company:
                res[ticker] = db_company.long_name

        return res

    def precalculate_cache(self):
        from api.comments.routes import get_comments_count

        if self.last_cache_date and self.age_cache_minutes() < 5:
            return

        no_comments = get_comments_count(str(self.id))

        update = {}
        if no_comments != self.no_comments:
            update['no_comments'] = no_comments

        pre_calc = self.precalculate_name_tickers()
        if pre_calc:
            update['named_exchange_tickers'] = pre_calc

        if update:
            update['last_cache_date'] = datetime.now()
            self.update(**update)
            self.reload()

    def __init__(self, *args, **kwargs):
        super(DB_News, self).__init__(*args, **kwargs)

    def update(self, *args, **kwargs):
        #mongo_prevalidate_fields(self)
        return super(DB_News, self).update(*args, **kwargs)

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

    def get_arguments_param(self, key, default=None):
        """ We will deprecate this eventually and hide better the raw AI function calls """
        try:
            return self['AI'][key]
        except:
            pass

        try:
            return self['tools'][0]['function']['arguments'][key]
        except:
            pass

        return default

    # Helpers to access the different things that we have a bit messed up at the moment.
    def get_title(self):
        if self.source_title:
            return self.source_title
        res = self.get_arguments_param("title", self.title)
        if not res:
            return ""

        return res

    def get_no_bullshit(self):
        res = self.get_arguments_param("no_bullshit", self.source_title)
        if not res:
            return self.get_title()

    def get_interest_score(self):
        return self.get_arguments_param("interest_score", 0)

    def get_paragraph(self):
        return self.get_arguments_param("paragraph", self.ai_summary[:80])

    def get_summary(self):
        return self.get_arguments_param("summary", self.ai_summary)

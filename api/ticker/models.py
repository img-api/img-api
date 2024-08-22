import os
import time
from datetime import datetime

from mongoengine import *

from imgapi_launcher import db

from flask import current_app
from flask_login import current_user
from api.user.user_check import DB_UserCheck

from api.query_helper import get_value_type_helper


class DB_FinancialMetrix(db.DynamicDocument):
    """ Class to create an event

    """
    meta = {
        'strict': False,
        'indexes': ['ticker', 'date'],
        "index_background": True,
    }

    ticker = db.StringField()
    date = db.DateTimeField()
    market_cap = db.FloatField()
    pe_ratio = db.FloatField()  # Price over earnings
    pb_ratio = db.FloatField()  # Price to book
    enterprise_value = db.FloatField()
    ev_ebitda = db.FloatField()  # Enterprise Value (EV) to its Earnings Before Interest
    peg_ratio = db.FloatField()  # Price/earnings to growth ratio


class DB_TickerPriceData(db.DynamicDocument):
    """
    """
    meta = {
        'strict': False,
        'indexes': ['ticker', 'date'],
        "index_background": True,
    }

    ticker = db.StringField()
    date = db.DateTimeField()

    current_price = db.FloatField()
    previous_close = db.FloatField()
    open = db.FloatField()
    day_high = db.FloatField()
    day_low = db.FloatField()
    volume = db.FloatField()
    week_high_52 = db.FloatField()
    week_low_52 = db.FloatField()


class DB_Company(db.DynamicDocument):
    """ Class to create a Company
    Large companies are in multiple exchanges.

    """
    meta = {
        'strict': False,
        'indexes': ['company_name'],
        "index_background": True,
    }

    company_name = db.StringField()
    country = db.StringField()
    sector = db.StringField()
    industry = db.StringField()

    wikipedia = db.StringField()

    def serialize(self):
        return mongo_to_dict_helper(self)


class DB_Ticker(db.DynamicDocument):
    """ Class to create a Ticker, a ticker can be in any exchange.

    """
    meta = {
        'strict': False,
        'indexes': ['ticker', 'company_name'],
        "index_background": True,
    }

    ticker = db.StringField()
    company_name = db.StringField()

    exchange = db.StringField()
    country = db.StringField()

    def serialize(self):
        return mongo_to_dict_helper(self)


class DB_TickerHighRes(db.DynamicDocument):
    """ Class to create an event

    """
    meta = {
        'strict': False,
        'indexes': ['ticker'],
        "index_background": True,
    }

    ticker = db.StringField()

    open = db.FloatField()
    high = db.FloatField()
    low = db.FloatField()
    close = db.FloatField()

    start = db.DateTimeField()
    end = db.DateTimeField()

    def serialize(self):
        return mongo_to_dict_helper(self)


class DB_TickerSimple(db.DynamicDocument):
    """ Class to create an event

    """
    meta = {
        'strict': False,
        "auto_create_index": True,
        "index_background": True,
    }

    ticker = db.StringField()
    close = db.FloatField()

    start = db.DateTimeField()

    def serialize(self):
        return mongo_to_dict_helper(self)
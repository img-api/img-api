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


class DB_Ticker(db.DynamicDocument):
    """ Class to create a Ticker, a ticker can be in any exchange.

    """
    meta = {
        'strict': False,
        'indexes': ['ticker', 'company_id', 'exchange'],
        "index_background": True,
    }

    ticker = db.StringField()
    company_id = db.StringField()

    exchange = db.StringField()
    country = db.StringField()

    info = db.DynamicField()

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


class DB_TickerUserOperation(db.DynamicDocument):
    """ Users can record transactions like buying and selling so they can track performance
        If they don't specify the price of acquisition or sale, it will generate automatically the value from market data.
    """
    meta = {
        'strict': False,
        "auto_create_index": True,
        "index_background": True,
    }

    ticker_id = db.StringField()
    is_sold = db.BooleanField()

    price_purchase = db.FloatField()
    price_sale = db.FloatField()

    total_shares = db.IntField()

    def serialize(self):
        return mongo_to_dict_helper(self)


class DB_TickerUserWatchlist(db.DynamicDocument):
    """ User can create lists and add special information """
    meta = {
        'strict': False,
        "auto_create_index": True,
        "index_background": True,
    }

    list_name = db.StringField()
    user_id = db.StringField()


class DB_TickerUserSubscription(db.DynamicDocument):
    """ User can suscribe tickers to lists """

    meta = {
        'strict': False,
        "auto_create_index": True,
        "index_background": True,
    }

    list_id = db.StringField()
    ticker = db.StringField()
    user_id = db.StringField()

    def serialize(self):
        return mongo_to_dict_helper(self)
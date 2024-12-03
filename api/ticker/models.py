from datetime import datetime, timedelta

from imgapi_launcher import db
from mongoengine import *


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
    status = db.StringField()
    company_id = db.StringField()

    # We run batches of processes, and we set the frequency of checks
    # so we can throttle the API calls according to the limits of the APIs we call to get info.
    last_processed_date = db.DateTimeField()
    force_reindex = db.BooleanField(defult=False)

    exchange = db.StringField()

    # TODO: This is a variable that we should populate depending on the exchange
    region = db.StringField()

    info = db.DynamicField()

    def reindex(self):
        if self.force_reindex:
            return

        threshold_date = datetime.now() - timedelta(days=2)
        if not self.last_processed_date or self.last_processed_date >= threshold_date:
            self.update(**{'force_reindex': True})

    def age_minutes(self, *args, **kwargs):
        age = (datetime.now() - self.last_processed_date).total_seconds() / 60
        print(self.ticker + " => " + str(age))
        return age

    def serialize(self):
        return mongo_to_dict_helper(self)

    def set_state(self, state_msg, dry_run=False):
        """ Update a processing state """
        if dry_run:
            return self

        self.update(**{
            'force_reindex': False,
            'status': state_msg,
            'last_processed_date': datetime.now()
        },
                    validate=False)

        self.reload()
        return self

    def query_exchange_ticker(full_symbol):
        from api.ticker.tickers_helpers import standardize_ticker_format

        if ":" not in full_symbol:
            full_symbol = standardize_ticker_format(full_symbol)

        p = full_symbol.split(":")
        query = Q(ticker=p[0]) & Q(exchange=p[1])
        return query

    def full_symbol(self):
        """ Helper to find our full_symbol, we also fix the MIC and Stock name confusion here """

        from api.ticker.tickers_helpers import standardize_ticker_format

        if not self.exchange:
            return self.ticker

        old_symbol = self.exchange + ":" + self.ticker
        full_symbol = standardize_ticker_format(old_symbol)

        if full_symbol != old_symbol:
            exchange, stock = full_symbol.split(':')
            update = {
                'exchange': exchange,
                'ticker': stock,
            }
            self.update(**update)

        return full_symbol

    def exchange_and_ticker(self):
        return self.full_symbol()

    def get_company(self):
        from api.company.models import DB_Company

        if not self.company_id:
            query = Q(exchange_tickers=exchange + ":" + ticker)
        else:
            query = Q(pk=self.company_id)

        db_company = DB_Company.objects(query).first()

        if not self.company_id and db_company:
            self.company_id = str(db_company.id)
            self.save(validate=False)

        return db_company

    def save(self, *args, **kwargs):
        ret = super(DB_Ticker, self).save(*args, **kwargs)
        return ret

    def set_state(self, state_msg):
        """ Update a processing state """
        self.update(**{'status': state_msg, 'last_processed_date': datetime.now()}, validate=False)
        return self


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
    """ Closest update in the system for 'realtime' data

    """
    meta = {
        'strict': False,
        "auto_create_index": True,
        "index_background": True,
    }

    company_name = db.StringField()
    exchange_ticker = db.StringField()
    last_update = db.DateTimeField()
    price = db.FloatField()
    ratio = db.FloatField()
    day_low = db.FloatField()
    day_high = db.FloatField()
    current_open = db.FloatField()
    previous_close = db.FloatField()
    volume = db.FloatField()
    bid = db.FloatField()
    bid_size = db.FloatField()

    def age_minutes(self, *args, **kwargs):

        age = (datetime.now() - self.last_update).total_seconds() / 60
        print(self.exchange_ticker + " => " + str(age))

        return age

    def save(self, *args, **kwargs):
        self.last_update = datetime.now()
        return super(DB_TickerSimple, self).save(*args, **kwargs)

    def update(self, *args, **kwargs):
        kwargs['last_update'] = datetime.now()
        ret = super(DB_TickerSimple, self).update(*args, **kwargs)
        return ret

    def serialize(self):
        return mongo_to_dict_helper(self)


class DB_TickerTimeSeries(db.DynamicDocument):
    """ Closest update in the system for 'realtime' data

    """
    meta = {
        'strict': False,
        "auto_create_index": True,
        "index_background": True,
    }

    exchange_ticker = db.StringField()
    price = db.FloatField()
    ratio = db.FloatField()
    day_low = db.FloatField()
    day_high = db.FloatField()
    current_open = db.FloatField()
    previous_close = db.FloatField()
    volume = db.FloatField()
    bid = db.FloatField()
    bid_size = db.FloatField()

    creation_date = db.DateTimeField()

    def age_minutes(self, *args, **kwargs):
        age = (datetime.now() - self.creation_date).total_seconds() / 60
        print(self.exchange_ticker + " => " + str(age))
        return age

    def save(self, *args, **kwargs):
        self.creation_date = datetime.now()
        return super(DB_TickerTimeSeries, self).save(*args, **kwargs)

    def update(self, *args, **kwargs):
        kwargs['creation_date'] = datetime.now()
        ret = super(DB_TickerTimeSeries, self).update(*args, **kwargs)
        return ret

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
    username = db.StringField()

    exchange_tickers = db.ListField(db.StringField(), default=[])


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

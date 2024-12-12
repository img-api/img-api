import base64
import time
import urllib.parse
from datetime import datetime

import rsa
from api.print_helper import *
from api.query_helper import *
from imgapi_launcher import db
from mongoengine import *


class DB_Company(db.DynamicDocument):
    meta = {
        'strict': False,
    }

    safe_name = db.StringField()

    company_name = db.StringField()
    headquarters = db.StringField()
    country = db.StringField()
    gics_sector = db.StringField()
    gics_sub_industry = db.StringField()

    creation_date = db.DateTimeField()
    last_update_date = db.DateTimeField()
    last_analysis_date = db.DateTimeField()

    # Convert into date
    founded = db.StringField()
    wikipedia = db.StringField()

    name = db.StringField()
    long_name = db.StringField()
    long_business_summary = db.StringField()

    email = db.StringField()
    main_address = db.StringField()
    main_address_1 = db.StringField()
    city = db.StringField()
    country = db.StringField()

    phone_number = db.StringField()
    zip_code = db.StringField()

    public_key = db.StringField()
    private_key = db.StringField()
    regex = db.StringField()
    CIK = db.IntField()

    # Where did we fetch the information
    source = db.StringField()

    ai_upload_date = db.DateTimeField()

    # List of exchanges in which this company trades, nasdaq, amex, etc
    exchanges = db.ListField(db.StringField(), default=list)

    # Tickers that belong to a company and an exchange
    exchange_tickers = db.ListField(db.StringField(), default=list)

    SAFE_KEYS = [
        "safe_name", "company_name", "country", "gics_sector", "gics_sub_industry", "name", "email", "main_address",
        "main_address_1", "phone_number"
    ]

    def __init__(self, *args, **kwargs):
        super(DB_Company, self).__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        if not self.creation_date:
            self.creation_date = datetime.now()

        self.last_update_date = datetime.now()

        if self.company_name:
            self.safe_name = self.get_safe_name(self.company_name)

        ret = super(DB_Company, self).save(*args, **kwargs)
        ret.reload()
        return ret

    def delete(self, *args, **kwargs):
        #abs_path = self.get_media_path() + self.file_path
        #if os.path.exists(abs_path):
        #    os.remove(abs_path)

        print_r(self.long_name + " DELETED " + str(self.exchange_tickers))
        return super(DB_Company, self).delete(*args, **kwargs)

    def set_key_value(self, key, value):
        # My own fields that can be edited:
        if not key.startswith('ia_') and not key.startswith('my_') and key not in self.SAFE_KEYS:
            return False

        return super(DB_Company, self).update(**{key: value})

    def serialize(self):
        """ Cleanup version of the media file so don't release confidential information """
        from api.ticker.tickers_helpers import ticker_exchanges_cleanup_dups

        res = mongo_to_dict_helper(self)

        et = ticker_exchanges_cleanup_dups(self['exchange_tickers'])
        res['exchange_tickers'] = et
        if len(et) != 0:
            res['primary_ticker'] = et[0]

        return res

    @staticmethod
    def get_safe_name(possible_name):
        """ Converts a title into a string that we can use for our database name, by removing all the extra characters
            [TODO] Check unicode values
        """
        possible_name = possible_name.strip().lower()
        prev = '_'

        clean = []

        for c in possible_name:
            s = ("" + c)
            if s.isalpha() or s.isalnum():
                clean.append(c)
                prev = c
                continue

            if prev == '_':
                continue

            prev = '_'
            clean.append(prev)

        if clean[-1] == '_':
            clean.pop()

        # The name has to be less than 24, so we don't hit an ID
        final = "".join(clean)[:23]
        return final

    def get_new_stamp(self):

        if not self.public_key:
            self.save()

        print("PUBLIC KEY " + self.public_key)

        publicKey = rsa.PublicKey.load_pkcs1(self.public_key)

        timestamp = str(time.time()).split(".")[0].encode()
        encoded_date = rsa.encrypt(timestamp, publicKey)

        encode = base64.encodebytes(encoded_date).decode("utf-8")

        safe_string = urllib.parse.quote_plus(encode)
        print("ENCODED " + safe_string)

        return safe_string

    def decode_stamp(self, stamp_str):

        print("Stamp " + stamp_str)

        stamp_str = urllib.parse.unquote(stamp_str)

        privateKey = rsa.PrivateKey.load_pkcs1(self.private_key)

        value = base64.b64decode(stamp_str)
        decoded_date = rsa.decrypt(value, privateKey)

        print("DECODED " + decoded_date.decode("ascii"))

        timestamp = int(decoded_date.decode("ascii"))
        current_time = time.time()

        diff = current_time - timestamp
        return diff

    def append_exchange(self, exchange, ticker=None):
        # We append an exchange for a company if it is not there.
        if not exchange:
            return

        exchange = exchange.upper()

        ex_update = False
        if exchange not in self.exchanges:
            ex_update = True
            self.exchanges.append(exchange)

        if ticker:
            ex = exchange + ":" + ticker
            if ex not in self.exchange_tickers:
                ex_update = True
                self.exchange_tickers.append(ex)

        if ex_update:
            self.save(validate=False)

    def get_primary_ticker(self):
        from api.ticker.tickers_helpers import standardize_ticker_format

        if len(self.exchange_tickers) == 0:
            return 'N/A'

        if len(self.exchange_tickers) == 1:
            return standardize_ticker_format(self.exchange_tickers[0])

        for et in self.exchange_tickers:
            if 'NMS:' not in et:
                return standardize_ticker_format(et)

        return standardize_ticker_format(self.exchange_tickers[-1])


class DB_CompanyPrompt(db.DynamicDocument):
    meta = {
        'strict': False,
        'allow_inheritance': True,
    }

    company_id = db.StringField()
    is_public = db.BooleanField(default=True)

    use_markdown = db.BooleanField(default=True)

    status = db.StringField()

    creation_date = db.DateTimeField()
    last_visited_date = db.DateTimeField()

    # List of articles to process or be added
    articles_id = db.ListField(db.StringField(), default=list)

    ai_summary = db.StringField()
    ai_upload_date = db.DateTimeField()

    prompt = db.StringField()

    type = db.StringField(default="prompt")

    force_reindex = db.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.creation_date:
            self.creation_date = datetime.now()

        ret = super(DB_CompanyPrompt, self).save(*args, **kwargs)
        return ret.reload()

    def update(self, *args, **kwargs):
        return super(DB_CompanyPrompt, self).update(*args, **kwargs)

    def delete(self, *args, **kwargs):
        print(" DELETED Company Prompt ")
        return super(DB_CompanyPrompt, self).delete(*args, **kwargs)

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

    def set_key_value(self, key, value):
        value = get_value_type_helper(self, key, value)

        update = {key: value}

        if update:
            self.update(**update, validate=False)

        return True

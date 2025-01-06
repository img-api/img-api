from datetime import datetime

from api.print_helper import *
from api.query_helper import *
from imgapi_launcher import db
from mongoengine import *


class DB_Telegram(db.DynamicDocument):
    meta = {
        'strict': False,
    }

    username = db.StringField()
    last_update_date = db.DateTimeField()

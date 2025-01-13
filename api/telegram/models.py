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


class DB_TelegramMessageQueue(db.DynamicDocument):
    meta = {
        'strict': False,
    }

    username = db.StringField()
    chat_id = db.StringField()

    status = db.StringField(default="WAIT_QUEUE")

    title = db.StringField()
    image_id = db.StringField()
    message = db.StringField()
    creation_date = db.DateTimeField()
    last_update_date = db.DateTimeField()

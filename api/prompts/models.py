from datetime import datetime

from api.print_helper import *
from api.query_helper import *
from api.user.user_check import DB_UserCheck
from imgapi_launcher import db
from mongoengine import *


class DB_UserPrompt(DB_UserCheck, db.DynamicDocument):
    meta = {
        'strict': False,
        'allow_inheritance': True,
    }

    username = db.StringField()

    # CHAT, PORTFOLIO, COMPANY, BOT...
    type = db.StringField()
    is_public = db.BooleanField(default=True)

    use_markdown = db.BooleanField(default=True)

    owner = db.StringField()
    status = db.StringField()

    creation_date = db.DateTimeField()
    last_visited_date = db.DateTimeField()

    # List of articles to process or be added
    articles_id = db.ListField(db.StringField(), default=list)
    related_exchange_tickers = db.ListField(db.StringField(), default=list)

    ai_summary = db.StringField()
    ai_upload_date = db.DateTimeField()

    prompt = db.StringField()
    assistant = db.StringField()
    system = db.StringField()
    system_name = db.StringField()

    type = db.StringField(default="user_prompt")
    subtype = db.StringField(default="")
    selection = db.ListField(db.StringField(), default=list)

    force_reindex = db.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.creation_date:
            self.creation_date = datetime.now()

        ret = super(DB_UserPrompt, self).save(*args, **kwargs)
        return ret.reload()

    def update(self, *args, **kwargs):
        return super(DB_UserPrompt, self).update(*args, **kwargs)


    def delete(self, *args, **kwargs):
        print(" DELETED User Prompt ")
        return super(DB_UserPrompt, self).delete(*args, **kwargs)

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

from datetime import datetime

from api.query_helper import DB_DateTimeFieldTimestamp
from api.user.user_check import DB_UserCheck
from imgapi_launcher import db
from mongoengine import *


class DB_Event(DB_UserCheck, db.DynamicDocument):
    """ Class to create an event

    """
    meta = {
        'strict': False,
        "auto_create_index": True,
        "index_background": True,
    }

    name = db.StringField()
    title = db.StringField()
    etype = db.StringField()

    parent_id = db.StringField()
    gallery_id = db.StringField()

    start_date = DB_DateTimeFieldTimestamp()
    end_date = DB_DateTimeFieldTimestamp()

    last_access_date = db.DateTimeField()

    progress = db.FloatField()      # Progress from 0 to 1
    priority = db.IntField()        # Position on the group list

    is_public = db.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.creation_date:
            self.creation_date = datetime.now()

        self.last_access_date = datetime.now()

        ret = super(DB_Event, self).save(*args, **kwargs)
        ret.reload()
        return ret

    def serialize(self):
        ret = mongo_to_dict_helper(self)
        return ret

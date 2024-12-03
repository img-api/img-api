from datetime import datetime

from imgapi_launcher import db
from mongoengine import *


class DB_Category(db.DynamicDocument):
    meta = {
        'strict': False,
    }

    owner_username = db.StringField()

    is_public = db.BooleanField(default=False)

    def __init__(self, *args, **kwargs):
        super(DB_Category, self).__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        if not self.creation_date:
            self.creation_date = datetime.now()

        ret = super(DB_Category, self).save(*args, **kwargs)
        ret.reload()
        return ret
z

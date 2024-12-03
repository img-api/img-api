from datetime import datetime

from imgapi_launcher import db


class DB_Channel(db.DynamicDocument):
    meta = {
        'strict': False,
    }

    creation_date = db.DateTimeField()
    last_update_date = db.DateTimeField()

    name = db.StringField()
    summary = db.StringField()

    def __init__(self, *args, **kwargs):
        super(DB_Channel, self).__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        if not self.creation_date:
            self.creation_date = datetime.now()

        ret = super(DB_Channel, self).save(*args, **kwargs)
        ret.reload()
        return ret

    def delete(self, *args, **kwargs):
        print(" DELETED Data ")
        return super(DB_Channel, self).delete(*args, **kwargs)

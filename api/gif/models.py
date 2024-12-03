from datetime import datetime

from imgapi_launcher import db


class DB_TenorGif(db.DynamicDocument):
    """ We store the documents that we download for third party websites so we can cache the API
    """
    meta = {
        'strict': False,
    }

    creation_date = db.DateTimeField()
    description = db.StringField()

    external_uuid = db.StringField()
    media_id = db.StringField()

    def __init__(self, *args, **kwargs):
        super(DB_TenorGif, self).__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        if not self.creation_date:
            self.creation_date = datetime.now()

        ret = super(DB_TenorGif, self).save(*args, **kwargs)
        return ret

    def delete(self, *args, **kwargs):
        return super(DB_TenorGif, self).delete(*args, **kwargs)

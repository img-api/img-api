from datetime import datetime
from enum import Enum

from imgapi_launcher import db


class AI_ProcessType(Enum):
    COMPANY_NEWS = 'company_news'
    PORTFOLIO = 'portfolio'
    PREDICTION = 'prediction'
    PERSONALITY = 'personality'
    SITE_COMMENT = 'site_comment'

class DB_AI_Process(db.DynamicDocument):
    meta = {
        'strict': False,
    }

    creation_date = db.DateTimeField()
    last_update_date = db.DateTimeField()

    source = db.StringField()
    username = db.StringField()

    # Portfolio news
    process_type = db.EnumField(AI_ProcessType, default=AI_ProcessType.COMPANY_NEWS)

    def __init__(self, *args, **kwargs):
        super(DB_AI_Process, self).__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        if not self.creation_date:
            self.creation_date = datetime.now()

        self.last_update_date = datetime.now()
        ret = super(DB_AI_Process, self).save(*args, **kwargs)
        ret.reload()
        return ret

    def delete(self, *args, **kwargs):
        print(" DELETED AI Process Data ")
        return super(DB_AI_Process, self).delete(*args, **kwargs)

    def set_key_value(self, key, value):
        # My own fields that can be edited:
        if not key.startswith('ia_') and not key.startswith('my_') and key not in self.SAFE_KEYS:
            return False

        return super(DB_AI_Process, self).update(**{key: value})

    def serialize(self):
        """ Cleanup version of the media file so don't release confidential information """
        serialized = {}

        for key in self:
            if self[key]:
                if key == 'id':
                    serialized[key] = str(self[key])
                else:
                    serialized[key] = self[key]

        return serialized

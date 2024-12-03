from imgapi_launcher import db


class DB_Tags(db.DynamicDocument):
    meta = {
        'strict': False,
    }

    tag = db.StringField()
    creation_date = db.DateTimeField()
    related = db.ListField(db.StringField())


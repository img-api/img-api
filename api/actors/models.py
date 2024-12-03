


from imgapi_launcher import db


class DB_Actor(db.DynamicDocument):
    """ An object, person, animal/model """
    meta = {
        'strict': False,
    }

    name = db.StringField()
    alternative_name = db.StringField()

    synonymous = db.ListField(db.StringField(), default=list)

    title = db.StringField()

    header = db.StringField()
    description = db.StringField()

    aka = db.StringField()
    url = db.StringField()
    is_NSFW = db.BooleanField(default=False)
    is_public = db.BooleanField(default=False)

    image_id = db.StringField()

    tags = db.ListField(db.StringField(), default=list)

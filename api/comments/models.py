import time
from datetime import datetime

from api.print_helper import *
from api.query_helper import *
from api.user.user_check import DB_UserCheck
from flask_login import current_user
from imgapi_launcher import db
from mongoengine import *


class DB_Comments(DB_UserCheck, db.DynamicDocument):
    """ Comment article
    """
    meta = {'strict': False, "index_background": True, 'indexes': ['username', 'parent_obj_id', 'parent_comment_id']}

    status = db.StringField()
    title = db.StringField()
    content = db.StringField()

    creation_date = db.DateTimeField()
    last_visited_date = db.DateTimeField()

    username = db.StringField()
    status = db.StringField()

    parent_obj = db.StringField()
    parent_obj_id = db.StringField()

    parent_comment_id = db.StringField()

    SAFE_KEYS = [
        "title", "content", "no_views", "no_likes", "no_dislikes", "parent_obj", "parent_obj_id", "parent_comment_id",
        "is_report", "subscription", "old_content", "old_title", "is_edited", "is_deleted",
    ]

    subscription = db.StringField()

    is_NSFW = db.BooleanField(default=False)
    is_edited = db.BooleanField(default=False)
    is_ghosted = db.BooleanField(default=False)
    is_moderated = db.BooleanField(default=False)
    is_report = db.BooleanField(default=False)
    is_deleted = db.BooleanField(default=False)

    no_views = db.LongField()
    no_likes = db.LongField()
    no_dislikes = db.LongField()

    def __init__(self, *args, **kwargs):
        super(DB_Comments, self).__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        if not self.creation_date:
            self.creation_date = datetime.now()

        self.username = current_user.username
        ret = super(DB_Comments, self).save(*args, **kwargs)
        return ret

    def set_key_value(self, key, value):
        if not self.is_current_user():
            return False

        # My own fields that can be edited:
        if not key.startswith('my_') and key not in self.SAFE_KEYS:
            return False

        value = get_value_type_helper(self, key, value)

        update = {key: value}

        if update:
            self.update(**update, validate=False)

        return True

    def delete(self, *args, **kwargs):
        print(" DELETED Comment Data ")
        return super(DB_Comments, self).delete(*args, **kwargs)

    def upvote(self):
        """Increases the rating of the comment by one."""
        self.rating += 1
        self.save()

    def downvote(self):
        """Decreases the rating of the comment by one."""
        self.rating -= 1
        self.save()

    @classmethod
    def check_data(cls, json):
        for key in json:
            if not key.startswith('my_') and key not in cls.SAFE_KEYS:
                return False

        # Check HTML tags using soap
        return True

    def update_with_checks(self, json):
        if not self.is_current_user():
            return False

        # My own fields that can be edited:
        update = {}
        for key in json:
            if not key.startswith('my_') and key not in self.SAFE_KEYS:
                continue

            value = get_value_type_helper(self, key, json[key])
            if key not in self or value != self[key]:
                update[key] = value

        if len(update) > 0:
            self.update(**update, validate=False)
            self.reload()

        return self.serialize()

    def serialize(self):
        """ Cleanup version so we don't release confidential information """
        serialized = {
            'id': str(self.id),
            'username': self.username,
            'parent_obj': self.parent_obj,
            'parent_obj_id': self.parent_obj_id,
            'parent_comment_id': self.parent_comment_id,

            'title': self.title,
            'content': self.content,
            'subscription': self.subscription,

            'is_NSFW': self.is_NSFW,
            'is_edited': self.is_edited,
            'is_report': self.is_report,

            'no_views': self.no_views,
            'no_likes': self.no_likes,
            'no_dislikes': self.no_dislikes,

            'creation_date': time.mktime(self.creation_date.timetuple()),
        }

        return serialized

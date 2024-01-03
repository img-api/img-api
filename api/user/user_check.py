from imgapi_launcher import db
from flask_login import current_user

from datetime import datetime


class DB_UserCheck():
    username = db.StringField()
    init_date = db.DateTimeField()
    creation_date = db.DateTimeField()

    def is_current_user(self):
        """ Returns if this media belongs to this user, so when we serialize we don't include confidential data """

        if not current_user.is_authenticated:
            return False

        if current_user.username == "admin":
            return True

        if self.username == current_user.username:
            return True

        return False

    def save(self, *args, **kwargs):
        if not self.init_date:
            self.init_date = datetime.now()

        if not self.creation_date:
            self.creation_date = datetime.now()

        if self.username != "admin":
            if not self.username:
                self.username = current_user.username

            elif self.username != current_user.username:
                return abort(401, "Unauthorized")

        ret = super(DB_UserCheck, self).save(*args, **kwargs)
        return ret
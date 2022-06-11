from imgapi_launcher import db
from flask_login import current_user


class DB_UserCheck():
    username = db.StringField()
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

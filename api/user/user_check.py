from datetime import datetime

from api.query_helper import get_value_type_helper
from flask import abort
from flask_login import current_user
from imgapi_launcher import db


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

        if 'is_admin' not in kwargs or kwargs['is_admin'] == False:
            self.check_parms(*args, **kwargs)

        ret = super(DB_UserCheck, self).save(*args, **kwargs)
        return ret

    def check_parms(self, *args, **kwargs):
        """ Checks and validates critical parameters so we don't get an user to change its username and replace another """
        if self.username and len(self.username) <= 3:
            print(" SYSTEM USER " + self.username)
            return True

        if self.username != "admin":
            if not self.username:
                self.username = current_user.username

            elif self.username != current_user.username:
                return abort(401, "Unauthorized")

        # Only admin can change an username
        if 'username' in kwargs and kwargs['username'] != current_user.username:
            return abort(401, "Unauthorized")

    def force_update(self, *args, **kwargs):
        ret = super(DB_UserCheck, self).update(*args, **kwargs)
        return ret

    def update(self, *args, **kwargs):
        if 'is_admin' not in kwargs or kwargs['is_admin'] == False:
            self.check_parms(*args, **kwargs)

        ret = super(DB_UserCheck, self).update(*args, **kwargs)
        return ret

    def set_key_value(self, key, value):
        if not self.is_current_user():
            return False

        # We don't let an user to update the username of an object
        #if key == "username" and current_user.username != "admin":
        #    return False

        if not self.creation_date:
            self.creation_date = datetime.now()

        value = get_value_type_helper(self, key, value)

        # No changes to the value, just return
        if value == self[key]:
            return True

        update = {key: value}
        if update:
            self.update(**update, validate=False)
            self.reload()

        return True

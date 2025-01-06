import os
import shutil
import time
from datetime import datetime, timedelta

from api.galleries.models import DB_UserGalleries
from api.media.models import File_Tracking
from api.print_helper import *
from api.query_helper import *
from api.query_helper import mongo_to_dict_helper
from api.tools.signature_serializer import BadSignature, SignatureExpired
from api.tools.signature_serializer import \
    TimedJSONWebSignatureSerializer as Serializer
from flask import current_app, json
from flask_login import UserMixin, current_user
from imgapi_launcher import db, login_manager
from mongoengine import *


class DB_UserSettings(db.DynamicEmbeddedDocument):
    send_email = db.BooleanField(default=False)


class DB_UserPayments(db.DynamicEmbeddedDocument):
    status = db.StringField(default=None)
    session_id = db.StringField()
    customer_id = db.StringField()
    subscription_id = db.StringField()
    product_id = db.StringField()
    payment_date = db.DateTimeField()
    expiration_date = db.DateTimeField()
    payment_total = db.FloatField()
    cancel_at_period_end = db.BooleanField(default=False)


@login_manager.user_loader
def user_loader(user_id):
    """ API for the  flask load manager to be able to search for our user in MongoDB """

    user = User.objects(pk=user_id).first()
    if user and user.is_active():
        return user
    else:
        print("Not active [%s]" % user_id)

    return None


class User(UserMixin, db.DynamicDocument):
    meta = {
        'strict': False,
    }

    def set_authenticated(self, value):
        if value:
            self._authenticated = True

    def is_active(self):
        return self.active

    creation_date = db.DateTimeField()
    last_access_date = db.DateTimeField()

    username = db.StringField(unique=True)
    email = db.StringField(unique=True)
    password = db.StringField()

    first_name = db.StringField(default="")
    last_name = db.StringField(default="")

    # Profile details
    company = db.StringField(default="")
    about_me = db.StringField(default="")
    phone_number = db.StringField(default="")
    address = db.StringField(default="")
    country = db.StringField(default="")
    city = db.StringField(default="")
    postal_code = db.StringField(default="")

    profile_mid = db.StringField()

    lang = db.StringField(default="EN")

    active = db.BooleanField(default=False)
    is_anon = db.BooleanField(default=False)

    # Can people see this user?
    is_public = db.BooleanField(default=True)

    # User uploads are public by default?
    is_media_public = db.BooleanField(default=False)
    is_admin = db.BooleanField(default=False)
    is_readonly = db.BooleanField(default=False)

    is_email_validated = db.BooleanField(default=False)

    current_subscription = db.StringField(default="")

    telegram_chat_id = db.StringField(default="")
    subscription = db.EmbeddedDocumentField(DB_UserPayments, default=None)

    list_payments = db.EmbeddedDocumentListField(DB_UserPayments, default=[])

    settings = db.EmbeddedDocumentField(DB_UserSettings, default=DB_UserSettings())
    galleries = db.EmbeddedDocumentField(DB_UserGalleries, default=DB_UserGalleries())

    last_email_date = db.DateTimeField()
    last_alert_date = db.DateTimeField()

    # TODO: Special entries for an user. This should be dynamic, or be in settings.
    my_debug_interface = db.BooleanField(default=False)
    my_email_summary = db.BooleanField(default=True)
    my_email_alerts_daily = db.BooleanField(default=True)

    # Users can modify directly fields which start with my_ or in the list of public variables
    public_keys = [
        "first_name", "last_name", "is_public", "is_media_public", "email", "lang", "company", "about_me", "address",
        "city", "country", "postal_code"
    ]

    def add_payment(self, product_id, customer_id, session_id, subscription_id, payment_total, months=1):

        try:
            # Just a check when we have to call the pay platform to see if we are still up to date in payments.
            expiration_days = 31 * months

            payment_date = datetime.utcnow()
            expiration_date = payment_date + timedelta(days=expiration_days)

            new_payment = DB_UserPayments(session_id=session_id,
                                          customer_id=customer_id,
                                          subscription_id=subscription_id,
                                          product_id=product_id,
                                          payment_date=payment_date,
                                          expiration_date=expiration_date,
                                          payment_total=payment_total)

            # Update the user model
            self.list_payments.append(new_payment)

            self.current_subscription = product_id
            self.subscription = new_payment
            self.save(validate=False)
            self.reload()

        except Exception as err:
            print_e(" CRASH saving payment! fuck! " + str(err))

        log_entry = {
            "session_id": session_id,
            "customer_id": customer_id,
            "product_id": product_id,
            "payment_date": payment_date.isoformat(),
            "expiration_date": expiration_date.isoformat(),
            "payment_total": payment_total,
            "timestamp": datetime.utcnow().isoformat()
        }

        log_file_path = "payments_log.json"
        with open(log_file_path, "a") as log_file:
            log_file.write(json.dumps(log_entry) + "\n")

        return True

    def check_in_usage(self):
        try:
            elapsed = datetime.utcnow() - self.last_access_date if self.last_access_date else None
            if not elapsed or elapsed.total_seconds() > 1200:
                if elapsed:
                    print_h1("SAVE USER UPDATE - ELAPSED " + str(elapsed.total_seconds()))

                if not self.creation_date:
                    self.creation_date = datetime.utcnow()

                self.last_access_date = datetime.utcnow()
                self.save(validate=False)

        except Exception as err:
            print_e(" CRASH saving last access " + str(err))

        return True

    def serialize(self):
        """ Returns a clean version of the user name so we have to explicitely add variables here
            We could return the object after a filter, but on this case,
            it is safer to never return from that source and convert directly into an object
        """
        if not self.creation_date:
            self.creation_date = datetime.utcnow()
            self.update(**{"creation_date": self.creation_date})

        ret = {
            'id': str(self.id),
            'username': self.username,
            'profile_mid': self.profile_mid,
            'lang': self.lang,
            'is_anon': self.is_anon,
            'is_public': self.is_public,
            'is_media_public': self.is_media_public,
            'is_valid': self.is_email_validated,
            'subscription': self.current_subscription,
            'creation_date': time.mktime(self.creation_date.timetuple()),
        }

        if self.subscription:
            subs_status = self.subscription.status
            if subs_status == 'active' and self.subscription.cancel_at_period_end:
                subs_status = "cancelled"

            ret['subscription_status'] = subs_status

        if self.is_admin or self.username == "admin":
            ret['is_admin'] = True

        # Confidential information only for the current user
        if current_user.is_authenticated:
            if current_user.username == self.username:
                ret['settings'] = mongo_to_dict_helper(self.settings)

                # My settings are dynamic and can be created by users to store personal information
                for key in self:
                    if (key.startswith("my_")):
                        ret[key] = self[key]

                for key in self.public_keys:
                    ret[key] = self[key]

        return ret

    # Tokens are valid for ~12 Months
    def generate_auth_token(self, expiration=(12 * 31 * 24 * 60 * 60), extra={}):
        print("- SERIALIZE APP KEY " + str(current_app.config['SECRET_KEY']))
        s = Serializer(current_app.config['SECRET_KEY'], expires_in=expiration)
        return s.dumps({'id': self.username, 'extra': extra}).decode("utf-8")

    @staticmethod
    def is_valid_token(request):
        print("------------ VALID TOKEN -----------")
        token = request.args.get("key")
        if not token:
            return None

        s = Serializer(current_app.config['SECRET_KEY'])

        try:
            data = s.loads(token)
        except BadSignature as bad_signature:
            print("[%s]" % bad_signature)
            if not isinstance(bad_signature, SignatureExpired):
                print(" Invalid valid token %s " % bad_signature.payload)
                return None

            print("------------ WARNING TOKEN EXPIRED -----------")
            data = bad_signature.payload

        user_id = data['id']
        user = User.objects(username=user_id).first()
        if user and user.is_active():
            return True

        return None

    @staticmethod
    def verify_auth_token(token, check_active=True):
        from api import get_response_error_formatted, get_response_formatted

        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except SignatureExpired:
            print(" Error: valid token, but expired ")
            return get_response_formatted(
                403, {'warning': 'Check Token Expired. System accepts expired tokens at the moment!'})

        except BadSignature:
            print(" Invalid valid token")
            return get_response_error_formatted(403, {'error_msg': 'Invalid token'})

        user_id = data['id']
        print("Token with user %s " % user_id)

        user = User.objects(username=user_id).first()
        if not user:
            return get_response_error_formatted(403, {'error_msg': 'User does not exist!'})

        if user.is_active():
            print("User Active [%s]" % user_id)
            return user

        return get_response_error_formatted(403, {'error_msg': 'User is not active!'})

    def delete_media(self):
        print(" FULL USER CLEAN UP - REMOVE FILES AND DATABASE ENTRIES ")

        # Delete every file that contains me
        File_Tracking.objects(username=self.username).delete()

        # Delete the entire folder path
        full_path = File_Tracking.get_media_path() + self.username + "/"

        if os.path.exists(full_path):
            shutil.rmtree(full_path)

    def delete(self, *args, **kwargs):
        print("--------------------------------------------------------")
        print(" DELETE USER " + self.username)
        print("--------------------------------------------------------")

        self.delete_media()
        self.galleries.clear_all(self.username)

        return super(User, self).delete(*args, **kwargs)

    def populate_media(self, media_list):
        """ Appends all the information from this user into the media files on the list """
        self.galleries.populate(media_list)

    def media_list_remove(self, gallery_id):
        if self.galleries.media_list_remove(gallery_id):
            self.save()

        return {"deleted": True}

    def get_photostream_position(self, media_id, position):
        stream_list = File_Tracking.objects(username=self.username)

        only_public = True
        if current_user.is_authenticated and self.username == current_user.username:
            only_public = False

        # Convert cursor into list
        found = -1
        for idx, item in enumerate(stream_list):
            if str(item.id) == media_id:
                found = idx
                break

        if found == -1:
            print_r(" Media not found on photostream wtf " + str(media_id))
            found = 0

        while position < len(stream_list):
            new_media = stream_list[(found + position) % len(stream_list)]
            if 'info' not in new_media:
                # We don't have info?... what?
                new_media.delete()
                position += 1
                continue

            if only_public and not new_media.is_public:
                position += 1
            else:
                return new_media

        return media_id

    def get_media_list(self, gallery_id, raw_db=False):
        """ Returns a dictionary with the media list """

        if gallery_id in ['', 'me', 'stream', 'undefined', 'null']:
            print_b(" No media list to return ")
            return None

        gallery = self.galleries.media_list_get(gallery_id, raw_db=raw_db)
        if not gallery:
            print_r(" Generate new gallery with this gallery_id " + str(gallery_id))

        return gallery

    def save(self, *args, **kwargs):
        ret = super(User, self).save(*args, **kwargs)
        ret.reload()
        return ret

    def action_on_list(self, media_id, action, media_list_short_name):
        """ Performs an interaction on a media list """
        update, ret = self.galleries.perform(media_id, action, media_list_short_name)

        if update:
            self.save(validate=False)

        return ret

    def set_on_list(self, gallery_id, param, value):
        """ Sets a parameter on the list  """

        return self.galleries.set(gallery_id, param, value)

    def get_random(self):
        covers = File_Tracking.objects(username=self.username, is_cover=True)
        return covers.first()

    def get_cover(self):
        if "my_cover" in self and self["my_cover"]:
            return self['my_cover']

        covers = File_Tracking.objects(username=self.username, is_cover=True)
        return covers.first()

    def get_background(self):
        if "my_cover" in self and self["my_cover"]:
            return self['my_cover']

        return self.get_random()

    def is_current_user(self):
        """ Returns if this media belongs to this user, so when we serialize we don't include confidential data """
        if not current_user.is_authenticated:
            return False

        if current_user.username == "admin":
            return True

        if self.username == current_user.username:
            return True

        return False

    def set_is_media_public(self, is_public):
        """ Changes all the media to public or private
            Quite dangerous, because the user will lose all the properties
        """

        privacy = File_Tracking.objects(username=self.username, is_public=not is_public)
        privacy.update(**{"is_public": is_public}, validate=False)

    def set_key_value(self, key, value, is_admin=False):
        # No checks if the user is admin
        if not is_admin:
            if not self.is_current_user():
                return False

            # My own fields that can be edited:
            if not key.startswith('my_') and key not in self.public_keys:
                return False

            # We don't let the user to change its name, but it should be already cought on the previous check for public_keys
            if key == "username":
                return False

        value = get_value_type_helper(self, key, value)

        if not hasattr(self, key) or value != self[key]:
            if key.startswith("my_"):
                self.update(**{key: value}, validate=False)
            else:
                self.update(**{key: value})
            self.reload()

        if key == "is_media_public":
            self.set_is_media_public(value)

        return True

    def update_with_checks(self, json):
        update = {}

        if not self.is_current_user():
            return False

        for key in json:
            value = json[key]

            # My own fields that can be edited:
            if not key.startswith('my_') and key not in self.public_keys:
                continue

            value = get_value_type_helper(self, key, value)

            if value == self[key]:
                continue

            update[key] = value
            if key == "is_media_public":
                self.set_is_media_public(value)

        if len(update) > 0:
            self.update(**update)
            self.reload()

        return True

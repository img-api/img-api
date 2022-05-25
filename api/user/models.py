import os
import time
import shutil
import datetime

from mongoengine import *
from api.print_helper import *

from flask import current_app
from flask_login import UserMixin, current_user

from imgapi_launcher import db, login_manager
from api.query_helper import mongo_to_dict_helper

from .signature_serializer import TimedJSONWebSignatureSerializer as Serializer, BadSignature, SignatureExpired

from .galleries import DB_UserGalleries
from api.media.models import File_Tracking


class DB_UserSubscription(db.DynamicEmbeddedDocument):
    category_id = db.StringField()
    update_date = db.DateTimeField()


class DB_UserSettings(db.DynamicEmbeddedDocument):
    send_email = db.BooleanField(default=False)


@login_manager.user_loader
def user_loader(user_id):
    """ API for the  flask load manager to be able to search for our user in MongoDB """

    user = User.objects(pk=user_id).first()
    if user and user.is_active():
        return user
    else:
        print("Not active [%s]" % user_id)

    return None


class User(UserMixin, db.Document):
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

    profile_img = db.StringField(default="")

    lang = db.StringField(default="EN")

    active = db.BooleanField(default=False)
    is_anon = db.BooleanField(default=False)
    is_public = db.BooleanField(default=True)

    settings = db.EmbeddedDocumentField(DB_UserSettings, default=DB_UserSettings())
    galleries = db.EmbeddedDocumentField(DB_UserGalleries, default=DB_UserGalleries())

    list_subscriptions = db.EmbeddedDocumentListField(DB_UserSubscription, default=[])

    def check_in_usage(self):
        from datetime import datetime
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
            self.creation_date = datetime.datetime.utcnow()
            self.update(**{"creation_date": self.creation_date})

        ret = {
            'username': self.username,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'profile_img': self.profile_img,
            'lang': self.lang,
            'is_anon': self.is_anon,
            'creation_date': time.mktime(self.creation_date.timetuple()),
        }

        # Confidential information only for the current user
        if current_user.is_authenticated:
            if current_user.username == self.username:
                ret['settings'] = mongo_to_dict_helper(self.settings)

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
        from api import get_response_formatted, get_response_error_formatted

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
            return media_id

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

        return self.galleries.media_list_get(gallery_id, raw_db=raw_db)

    def action_on_list(self, media_id, action, media_list_short_name):
        """ Performs an interaction on a media list """
        update, ret = self.galleries.perform(media_id, action, media_list_short_name)

        if update:
            self.save()

        return ret

    def set_on_list(self, gallery_id, param, value):
        """ Sets a parameter on the list  """

        return self.galleries.set(gallery_id, param, value)

import os
import datetime

from mongoengine import *

from flask import current_app
from flask_login import UserMixin

from imgapi_launcher import db, login_manager
from itsdangerous import (TimedJSONWebSignatureSerializer as Serializer, BadSignature, SignatureExpired)
from api import get_response_formatted, get_response_error_formatted


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

    def is_authenticated(self):
        print(" is_authenticated ")
        return self._authenticated

    def is_active(self):
        return self.active

    def is_anonymous(self):
        print(" is_anonymous ")
        return False

    date_creation = db.DateTimeField()
    last_access_date = db.DateTimeField()

    username = db.StringField(unique=True)

    first_name = db.StringField(default="")
    last_name = db.StringField(default="")

    email = db.StringField(unique=True)
    password = db.StringField()

    lang = db.StringField()

    active = db.BooleanField(default=False)

    # Tokens are valid for ~12 Months
    def generate_auth_token(self, expiration=(12 * 31 * 24 * 60 * 60), extra={}):
        print("- SERIALIZE APP KEY " + str(current_app.config['SECRET_KEY']))
        s = Serializer(current_app.config['SECRET_KEY'], expires_in=expiration)
        return s.dumps({'id': self.username, 'db': self.database, 'extra': extra}).decode("utf-8")

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
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except SignatureExpired:
            print(" Error: valid token, but expired ")
            return get_response_formatted(
                {'warning': 'Check Token Expired. System accepts expired tokens at the moment!'}), None

        except BadSignature:
            print(" Invalid valid token")
            return get_response_error_formatted(403, {'error_msg': 'Invalid token'}), None

        user_id = data['id']
        print("Token with user %s " % user_id)

        user = User.objects(username=user_id).first()
        if not user:
            return get_response_error_formatted(403, {'error_msg': 'User does not exist!'}), None

        if user.is_active():
            print("User Active [%s]" % user_id)
            return user

        return get_response_error_formatted(403, {'error_msg': 'User is not active!'}), None
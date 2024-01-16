import os
import rsa
import time
import base64
import shutil
from datetime import datetime

import urllib.parse

from mongoengine import *
from api.print_helper import *
from api.query_helper import *

from flask import current_app
from flask_login import UserMixin, current_user

from imgapi_launcher import db, login_manager
from api.query_helper import mongo_to_dict_helper

from api.tools.signature_serializer import TimedJSONWebSignatureSerializer as Serializer, BadSignature, SignatureExpired

from api.galleries.models import DB_UserGalleries
from api.user.user_check import DB_UserCheck


class DB_Business(DB_UserCheck, db.DynamicDocument):
    meta = {
        'strict': False,
    }

    safe_name = db.StringField()
    name = db.StringField()
    email = db.StringField()
    main_address = db.StringField()
    main_address_1 = db.StringField()
    phone_number = db.StringField()

    public_key = db.StringField()
    private_key = db.StringField()

    SAFE_KEYS = ["name", "email", "main_address", "main_address_1", "phone_number"]

    def __init__(self, *args, **kwargs):
        super(DB_Business, self).__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        if not self.creation_date:
            self.creation_date = datetime.now()

        if not self.username:
            self.username = current_user.username

        if not self.public_key:
            public, private = rsa.newkeys(512)

            self.public_key = public.save_pkcs1().decode('utf-8')
            self.private_key = private.save_pkcs1().decode('utf-8')

        self.safe_name = self.get_safe_name(self.name)
        ret = super(DB_Business, self).save(*args, **kwargs)
        ret.reload()
        return ret

    def delete(self, *args, **kwargs):
        #abs_path = self.get_media_path() + self.file_path
        #if os.path.exists(abs_path):
        #    os.remove(abs_path)

        print(" DELETED Business Data ")
        return super(DB_Business, self).delete(*args, **kwargs)

    def set_key_value(self, key, value):
        # My own fields that can be edited:
        if not key.startswith('my_') and key not in self.SAFE_KEYS:
            return False

        return super(DB_Business, self).set_key_value(key, value)

    def serialize(self):
        """ Cleanup version of the media file so don't release confidential information """
        serialized = {}

        for key in self:
            if (key.startswith('my_') and self[key]) or key in self.SAFE_KEYS:
                serialized[key] = self[key]

        return serialized

    @staticmethod
    def get_safe_name(possible_name):
        """ Converts a title into a string that we can use for our database name, by removing all the extra characters
            [TODO] Check unicode values
        """
        possible_name = possible_name.strip().lower()
        prev = '_'

        clean = []

        for c in possible_name:
            s = ("" + c)
            if s.isalpha() or s.isalnum():
                clean.append(c)
                prev = c
                continue

            if prev == '_':
                continue

            prev = '_'
            clean.append(prev)

        if clean[-1] == '_':
            clean.pop()

        # The name has to be less than 24, so we don't hit an ID
        final = "".join(clean)[:23]
        return final

    def get_new_stamp(self):

        if not self.public_key:
            self.save()

        print("PUBLIC KEY " + self.public_key)

        publicKey = rsa.PublicKey.load_pkcs1(self.public_key)

        timestamp = str(time.time()).split(".")[0].encode()
        encoded_date = rsa.encrypt(timestamp, publicKey)

        encode = base64.encodebytes(encoded_date).decode("utf-8")

        safe_string = urllib.parse.quote_plus(encode)
        print("ENCODED " + safe_string)

        return safe_string

    def decode_stamp(self, stamp_str):

        print("Stamp " + stamp_str)

        stamp_str = urllib.parse.unquote(stamp_str)

        privateKey = rsa.PrivateKey.load_pkcs1(self.private_key)

        value = base64.b64decode(stamp_str)
        decoded_date = rsa.decrypt(value, privateKey)

        print("DECODED " + decoded_date.decode("ascii"))

        timestamp = int(decoded_date.decode("ascii"))
        current_time = time.time()

        diff = current_time - timestamp
        return diff

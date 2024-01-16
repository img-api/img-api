import re
import os
import time
import random
import shutil

from mongoengine import *
from api.print_helper import *
from api.query_helper import *

from flask import current_app, abort
from flask_login import UserMixin, current_user

from imgapi_launcher import db, login_manager
from api.query_helper import mongo_to_dict_helper
from api.user.user_check import DB_UserCheck
from api.query_helper import get_value_type_helper

from api.tools.signature_serializer import TimedJSONWebSignatureSerializer as Serializer, BadSignature, SignatureExpired


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

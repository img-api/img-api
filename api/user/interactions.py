import os
import time
import shutil
from datetime import datetime

from mongoengine import *
from api.print_helper import *

from flask import current_app
from flask_login import UserMixin, current_user

from imgapi_launcher import db, login_manager
from api.query_helper import mongo_to_dict_helper

from .signature_serializer import TimedJSONWebSignatureSerializer as Serializer, BadSignature, SignatureExpired


class DB_ItemMedia(db.DynamicEmbeddedDocument):
    media_id = db.StringField()
    update_date = db.DateTimeField()


class DB_MediaList(db.Document):
    username = db.StringField(unique=True)
    list_type = db.StringField()
    media_list = db.EmbeddedDocumentListField(DB_ItemMedia, default=[])

    def find_on_list(self, media_id):
        for idx, item in enumerate(self.media_list):
            if item.media_id == media_id:
                return idx

        return -1

    def is_on_list(self, media_id):
        return self.find_on_list(self, media_id) != -1

    def convert_to_dict(self):
        ret = {}
        for item in self.media_list:
            ret[item.media_id] = item.update

        return ret

    def add_to_list(self, media_id):
        """ Adds to a list if it doesn't have the media """

        if self.find_on_list(self.media_list) != -1:
            return False

        item = DB_ItemMedia({"media_id": media_id, "update_date": datetime.now()})

        self.media_list.append(item)
        return True

    def remove_from_list(self, media_id):
        """ Remove from a list of media """

        res = self.find_on_list(self.media_list)
        if res == -1:
            return False

        self.media_list.pop(res)
        return True


class DB_UserInteractions(db.DynamicEmbeddedDocument):
    list_favs_id = db.StringField()
    list_likes_id = db.StringField()
    list_dislikes_id = db.StringField()

    def get_media(self, list_id):
        return DB_MediaList.objects(pk=list_id).first()

    def get_dict(self, list_id):
        res = self.get_media(list_id)
        if not res: return {}
        return res.convert_to_dict()

    def serialize(self):
        """ Return the media in dictionaries for quick frontend access """

        ret = {
            'likes': self.get_dict(self.list_likes),
            'dislikes': self.get_dict(self.list_dislikes),
            'favs': self.get_dict(self.list_favs),
        }

    def is_on_list(self, list_id, media):
        if not list_id:
            return False

        media_list = self.get_media(list_id)
        if not media_list:
            return False

        return media_list

    def populate(self, media_list):
        """ Adds if the user liked or disliked the media """

        for media in media_list:
            m_id = media['media_id']

            if self.is_on_list(m_id, self.list_favs_id):
                media['fav'] = True

            if self.is_on_list(m_id, self.list_likes_id):
                media['like'] = True

            if self.is_on_list(m_id, self.list_dislikes_id):
                media['dislike'] = True

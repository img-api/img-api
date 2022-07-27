import os
import time
import datetime

from mongoengine import *

from imgapi_launcher import db

from flask import current_app
from flask_login import current_user

from api.query_helper import get_value_type_helper
from api.user.user_check import DB_UserCheck


class File_Tracking(DB_UserCheck, db.DynamicDocument):
    meta = {
        'strict': False,
        "auto_create_index": False,
        "index_background": True,
        'indexes': ['username', 'tags', 'creation_date']
    }

    file_format = db.StringField()

    file_name = db.StringField()
    file_path = db.StringField()
    file_type = db.StringField(default='image')
    file_size = db.LongField()

    checksum_md5 = db.StringField()

    #### Edit attributes are editable by the user without ####

    my_title = db.StringField()
    my_header = db.StringField()

    my_description = db.StringField()
    my_source_url = db.StringField()
    my_gallery_id = db.StringField()

    # A helper to specify if a preview was generated
    has_preview = db.BooleanField(default=False)

    # Did we process this file with our services
    processed = db.BooleanField(default=False)

    is_NSFW = db.BooleanField(default=False)
    is_anon = db.BooleanField(default=False)
    is_cover = db.BooleanField(default=False)
    is_public = db.BooleanField(default=False)
    is_unlisted = db.BooleanField(default=False)
    is_profile = db.BooleanField(default=False)

    no_views = db.LongField()
    no_likes = db.LongField()
    no_dislikes = db.LongField()

    comments = db.ListField(db.StringField())
    tags = db.ListField(db.StringField(), default=list)
    auto_tags = db.ListField(db.StringField(), default=list)

    actors = db.ListField(db.StringField(), default=list)

    SAFE_KEYS = ["is_cover", "is_public", "is_unlisted", "tags", "is_profile", "is_NSFW"]

    def __init__(self, *args, **kwargs):
        super(File_Tracking, self).__init__(*args, **kwargs)

    @staticmethod
    def get_media_path():
        media_path = current_app.config.get('MEDIA_PATH')
        if not media_path:
            abort(500, "Internal error, application MEDIA_PATH is not configured!")

        return media_path

    @staticmethod
    def is_extension_image(file_format, image_list=[".JPEG", ".JPG", ".GIF", ".GIFV", ".PNG", ".BMP", ".TGA", ".WEBP"]):
        if file_format[0] != '.': file_format = "." + file_format
        if file_format in image_list:
            return True

        return False

    @staticmethod
    def is_extension_video(file_format, video_list=['.MP4', '.MPEG', '.AVI', '.MOV', 'WMV', '.3GP', '.M4V']):
        if file_format[0] != '.': file_format = "." + file_format
        if file_format in video_list:
            return True

        return False

    def is_image(self):
        return self.is_extension_image(self.file_format)

    def is_video(self):
        return self.is_extension_video(self.file_format)

    def save(self, *args, **kwargs):
        if not self.creation_date:
            self.creation_date = datetime.datetime.now()

        ret = super(File_Tracking, self).save(*args, **kwargs)
        ret.reload()
        return ret

    def delete(self, *args, **kwargs):
        abs_path = self.get_media_path() + self.file_path
        if os.path.exists(abs_path):
            os.remove(abs_path)

        print(" FILE DELETED ")
        return super(File_Tracking, self).delete(*args, **kwargs)

    def exists(self):
        abs_path = self.get_media_path() + self.file_path
        if not os.path.exists(abs_path):
            print(" FILE NOT FOUND - DELETE DATABASE ENTRY ")
            self.delete()
            return False

        return True

    def is_private(self):
        """ Lexical helper """
        return not self.is_public

    def get_owner(self):
        from api.user.models import User

        if not self.is_public:
            return None

        return User.objects(username=self.username).first()

    def set_key_value(self, key, value):
        if not self.is_current_user():
            return False

        # My own fields that can be edited:
        if not key.startswith('my_') and key not in self.SAFE_KEYS:
            return False

        value = get_value_type_helper(self, key, value)

        update = {key: value}

        if key == 'is_unlisted' and value == True:
            update['is_public'] = True

        if update:
            self.update(**update, validate=False)

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

            if key == "is_profile":
                current_user.update(**{"profile_mid": str(self.id)})

        if len(update) > 0:
            self.update(**update, validate=False)
            self.reload()

        return self.serialize()

    def serialize(self):
        """ Cleanup version of the media file so don't release confidential information """
        serialized_file = {
            'is_public': self.is_public,
            'is_anon': self.is_anon,
            'is_cover': self.is_cover,
            'is_profile': self.is_profile,
            'is_unlisted': self.is_unlisted,
            'is_NSFW': self.is_NSFW,
            'file_size': self.file_size,
            'file_type': self.file_type,
            'file_format': self.file_format,
            'username': self.username,
            'media_id': str(self.id),
            'creation_date': time.mktime(self.creation_date.timetuple()),
            'actors': self.actors,
            'tags': self.tags,
            'auto_tags': self.auto_tags,
        }

        for key in self:
            if key.startswith('my_') and self[key]:
                serialized_file[key] = self[key]

        if 'info' in self:
            serialized_file['info'] = self['info']

        if self.is_current_user():
            serialized_file.update({
                'file_name': self.file_name,
                'file_path': self.file_path,
                'checksum_md5': self.checksum_md5,
            })

        return serialized_file

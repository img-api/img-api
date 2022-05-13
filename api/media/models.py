import os
import time
import datetime

from mongoengine import *

from imgapi_launcher import db

from flask import current_app
from flask_login import current_user


class File_Tracking(db.DynamicDocument):
    meta = {
        'strict': False,
    }

    creation_date = db.DateTimeField()
    file_format = db.StringField()

    file_name = db.StringField()
    file_path = db.StringField()
    file_type = db.StringField(default='image')
    file_size = db.LongField()

    checksum_md5 = db.StringField()
    username = db.StringField()

    # A helper to specify if a preview was generated
    has_preview = db.BooleanField(default=False)

    # Did we process this file with our services
    processed = db.BooleanField(default=False)

    is_public = db.BooleanField(default=False)
    is_anon = db.BooleanField(default=False)

    comments = db.ListField(db.StringField())

    @staticmethod
    def get_media_path():
        media_path = current_app.config.get('MEDIA_PATH')
        if not media_path:
            abort(500, "Internal error, application MEDIA_PATH is not configured!")

        return media_path

    def __init__(self, *args, **kwargs):
        super(File_Tracking, self).__init__(*args, **kwargs)

    def is_image(self):
        image_list = [".JPEG", ".JPG", ".GIF", ".GIFV", ".PNG", ".BMP", ".TGA", ".WEBP"]
        if self.file_format in image_list:
            return True

        return False

    def is_video(self):
        video_list = ['MP4', 'MPEG', 'AVI', 'MOV', 'WMV', '3GP', 'M4V']
        if self.file_format in video_list:
            return True

        return False

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

    def is_current_user(self):
        """ Returns if this media belongs to this user, so when we serialize we don't include confidential data """
        if not current_user.is_authenticated:
            return False

        if self.username == current_user.username:
            return True

        return False

    def serialize(self):
        """ Cleanup version of the media file so don't release confidential information """
        serialized_file = {
            'is_public': self.is_public,
            'is_anon': self.is_anon,
            'file_size': self.file_size,
            'file_type': self.file_type,
            'file_format': self.file_format,
            'username': self.username,
            'media_id': str(self.id),
            'creation_date': time.mktime(self.creation_date.timetuple()),
        }

        if 'info' in self:
            serialized_file['info'] = self['info']

        if self.is_current_user():
            serialized_file.update({
                'file_name': self.file_name,
                'file_path': self.file_path,
                'checksum_md5': self.checksum_md5,
            })

        return serialized_file

import os
import datetime

from mongoengine import *

from imgapi_launcher import db

class File_Tracking(db.DynamicDocument):
    meta = {
        'strict': False,
    }

    creation_date = db.DateTimeField()
    file_format = db.StringField()

    file_name = db.StringField()
    file_path = db.StringField()
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

    def __init__(self, *args, **kwargs):
        super(File_Tracking, self).__init__(*args, **kwargs)
        self.creation_date = datetime.datetime.now()

    def is_image(self):
        image_list = [".JPEG", ".JPG", ".GIF", ".GIFV", ".PNG", ".BMP", ".TGA"]
        if self.file_format in image_list:
            return True

        return False

    def is_video(self):
        video_list = ['MP4', 'MPEG', 'AVI', 'MOV', 'WMV', '3GP', 'M4V']
        if self.file_format in video_list:
            return True

        return False

    def save(self, *args, **kwargs):
        ret = super(File_Tracking, self).save(*args, **kwargs)
        ret.reload()
        return ret

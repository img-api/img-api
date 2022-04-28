import os
import datetime

from mongoengine import *

from app import db

class File_Tracking(db.DynamicEmbeddedDocument):
    meta = {
        'strict': False,
    }

    creation_date = db.DateTime()
    file_format = db.StringField()

    file_name = db.StringField()
    file_path = db.StringField()
    file_size = db.LongField()

    checksum_md5 = db.StringField()
    user_name = db.StringField()

    # A helper to specify if a preview was generated
    has_preview = db.BooleanField()

    # Did we process this file with our services
    processed = db.BooleanField()
    is_public = db.BooleanField()

    comments = db.ListField(db.StringField())

    def is_image(self):
        image_list = [".JPEG", ".JPG", ".GIF", ".GIFV", ".PNG", ".BMP", ".TGA"]
        if self.file_format in image_list:
            # TODO Check if file is correct by calling a third party process
            self.save(validate=False)
            return True

        return False


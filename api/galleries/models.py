import random
from datetime import datetime

from api.print_helper import *
from api.query_helper import *
from api.query_helper import get_value_type_helper, mongo_to_dict_helper
from api.user.user_check import DB_UserCheck
from flask import abort
from flask_login import current_user
from imgapi_launcher import db
from mongoengine import *


class DB_ItemMedia(db.DynamicEmbeddedDocument):
    media_id = db.StringField()
    update_date = db.DateTimeField()


class DB_MediaList(db.DynamicDocument, DB_UserCheck):
    """ A media list is a collection of items that an user likes, dislikes, or are a in a playlist """
    meta = {
        'strict': False,
    }

    list_type = db.StringField()

    name = db.StringField()
    title = db.StringField()
    header = db.StringField()
    description = db.StringField()

    cover_id = db.StringField()
    background_id = db.StringField()

    is_NSFW = db.BooleanField(default=False)
    is_public = db.BooleanField(default=False)
    is_unlisted = db.BooleanField(default=False)
    is_order_asc = db.BooleanField(default=True)

    allow_public_upload = db.BooleanField(default=False)
    tags = db.ListField(db.StringField(), default=list)

    media_list = db.EmbeddedDocumentListField(DB_ItemMedia, default=[])

    private_keys = []

    def find_media_pos(self, media_id, position):
        for idx, item in enumerate(self.media_list):
            if item.media_id == media_id:
                pos = (idx + position) % len(self.media_list)
                return pos

        return 0

    def get_media_position(self, media_id, position):
        from api.media.models import File_Tracking

        media_file = None

        remove_cleanup = []

        pos = self.find_media_pos(media_id, position)

        try:
            while position < len(self.media_list):
                item = self.media_list[pos]
                media_file = File_Tracking.objects(id=item.media_id).first()

                if not media_file:
                    remove_cleanup.append(item.media_id)

                if media_file: return media_file

                position += 1
                pos = (pos + position) % len(self.media_list)

            return None
        finally:
            for mid in remove_cleanup:
                print_r(" Media was deleted , we have to remove it from this list ")
                self.remove_from_list(mid)

    def get_position(self, media_id, position):
        for idx, item in enumerate(self.media_list):
            if item.media_id == media_id:
                pos = (idx + position) % len(self.media_list)
                return self.media_list[pos]

        return self.media_list[0]

    def find_on_list(self, media_id):
        for idx, item in enumerate(self.media_list):
            if item.media_id == media_id:
                return idx

        return -1

    def is_on_list(self, media_id):
        return self.find_on_list(media_id) != -1

    def convert_to_dict(self):
        ret = {}
        for item in self.media_list:
            ret[item.media_id] = item.update_date

        return ret

    def serialize(self):
        ret = mongo_to_dict_helper(self, filter_out=['media_list'])

        return ret

    def add_to_list(self, media_id):
        """ Adds to a list if it doesn't have the media """

        if self.find_on_list(media_id) != -1:
            print_r(" Duplicated ")
            return False

        item = DB_ItemMedia(**{"media_id": media_id, "update_date": datetime.now()})

        # First item on the list will be the media cover
        if len(self.media_list) == 0 or not self.cover_id:
            self.set_cover(media_id)

        # Second item will be the background. Users can change them with the API
        if len(self.media_list) == 1:
            self.set_background(media_id)

        self.media_list.append(item)
        self.save()
        return True

    def remove_from_list(self, media_id):
        """ Remove from a list of media """

        if self.cover_id == media_id:
            self.set_cover(None)

        if self.background_id == media_id:
            self.set_background(None)

        res = self.find_on_list(media_id)
        if res == -1:
            return False

        self.media_list.pop(res)
        self.save()
        return True

    def check_permissions(self):
        pass

        if self.allow_public_upload:
            return True

        if not self.is_public and not self.is_current_user():
            return abort(401, "Unauthorized")

        return True

    def get_as_list(self):
        return [media['media_id'] for media in self.media_list]

    def set_cover(self, media_id):
        """ Galleries have a cover """
        self.update(**{"cover_id": media_id})

    def set_background(self, media_id):
        """ Galleries have a background which is also used when a large image has to be displayed  """
        self.update(**{"background_id": media_id})

    def set_media_privacy(self, is_public):
        """ If we change a gallery permissions, all the media will adjust to it """
        from api.media.routes import api_media_set_privacy

        print_b(" Special case in which we toggle all the items on the gallery ")
        my_list = self.get_as_list()
        for media_id in my_list:
            api_media_set_privacy(media_id, is_public)

    def set_media_unlisted(self, is_unlisted):
        """ Unlisted media is visible but only if you have the link to the media """
        from api.media.routes import api_media_set_unlisted

        my_list = self.get_as_list()
        for media_id in my_list:
            api_media_set_unlisted(media_id, is_unlisted)

    def update_with_checks(self, json):
        update = {}

        if not self.is_current_user():
            return False

        for key in json:
            value = json[key]

            if key in self.private_keys:
                continue

            value = get_value_type_helper(self, key, value)

            if value == self[key]:
                continue

            update[key] = value

        if len(update) > 0:
            self.update(**update)
            self.reload()

        return True


class DB_UserGalleries(db.DynamicEmbeddedDocument):
    """ User interaction is every item that the user wants to store as a collection
        User stores media lists, which are just lists of IDs and media with special information.

        They might be building a list of favourite wedding dresses, or whatever.

        We have our default media collections which are Favourites "favs", likes and dislikes.
        The rest of collections are dynamic.

        Users should have a limit in the amount of collections they can create.
    """

    def get_media_list(self, list_id):
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

    def is_on_list(self, media_id, media_list_name):
        if not media_id or not media_list_name:
            return False

        if media_list_name not in self:
            return False

        media_list = self.get_media_list(self[media_list_name])
        if not media_list:
            return False

        return media_list.is_on_list(media_id)

    def get_media_list_by_name_or_id(self, media_list_id):
        if len(media_list_id) == 24:
            return self.get_media_list(media_list_id)

        name_id = "list_" + media_list_id + "_id"
        if (name_id in self or hasattr(self, name_id)) and self[name_id]:
            return self.get_media_list(self[name_id])

        return None

    def perform(self, media_id, action, media_list_short_name):
        """ Executes an action on the user's media lists
            Current available actions are:
                - Append a media
                - Remove a media
                - Set Cover and Background
        """

        if action not in ['append', 'remove', 'toggle', 'set_cover', 'set_background']:
            return False, {'action': 'error', 'error_msg': "Action unknown"}

        is_favs = (media_list_short_name == "favs")

        media_list = self.get_media_list_by_name_or_id(media_list_short_name)
        if not media_list:
            if len(media_list_short_name) == 24:
                return abort(400, "Wrong media name")

            name_id = "list_" + media_list_short_name + "_id"
            media_list = DB_MediaList(**{
                "name": media_list_short_name,
                "username": current_user.username,
                "list_type": media_list_short_name
            })
            if not media_list:
                return abort(404, "Not found")

            media_list.save().reload()

            self[name_id] = str(media_list.id)

        media_list.check_permissions()

        if action == "toggle":
            if media_list.is_on_list(media_id):
                action = "remove"
            else:
                action = "append"

        if action == "append":
            media_list.add_to_list(media_id)
            if is_favs:
                action = "set_cover"

        elif action == "remove":
            media_list.remove_from_list(media_id)

        if action == "set_cover":
            media_list.set_cover(media_id)

        if action == "set_background":
            media_list.set_background(media_id)

        return True, {'action': 'success', 'media_list_id': str(media_list.id)}

    def get_list_id(self, name_or_id):
        if len(name_or_id) != 24:
            if not name_or_id.startswith("list_"):
                name_or_id = "list_" + name_or_id + "_id"

            if not name_or_id in self:
                return None

            return self[name_or_id]

        return name_or_id

    @staticmethod
    def get_safe_gallery_name(possible_name):
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

    def exists(self, name_or_id):
        list_id = self.get_list_id(name_or_id)
        if not list_id:
            return False

        return True

    def remove_list_entry(self, list_id):
        found_key = None
        for key, value in self.__dict__.items():
            if value == list_id:
                self[key] = None
                found_key = key
                break

        if found_key:
            self.__dict__.pop(key, None)
            return True

        return False

    def media_list_remove(self, list_id):
        list_id = self.get_list_id(list_id)
        if not list_id:
            return abort(404, "Media list not found")

        self.remove_list_entry(list_id)

        my_list = DB_MediaList.objects(pk=list_id).first()
        if not my_list:
            print_r(" Gallery doesn't exist anymore.")
            return True

        if my_list.username != current_user.username:
            print_r(" User is not owner, cannot delete only unsubscribe.")
            return True

        my_list.delete()
        return True

    def media_list_get(self, list_gallery_id, image_type=None, raw_db=False):
        """ Gets a media list, if there is not one and it is not a MongoID, we generate a gallery automatically """
        list_id = self.get_list_id(list_gallery_id)

        my_list = None
        if not list_id:
            if len(list_gallery_id) != 24:
                # Auto create gallery
                my_list = self.create(current_user.username, list_gallery_id, {'title': list_gallery_id})
                if raw_db:
                    return my_list

            if not my_list:
                return {'is_empty': True, 'media_list': []}

        if not my_list:
            my_list = DB_MediaList.objects(pk=list_id).first()

        if not my_list:
            return None

        my_list.check_permissions()

        if raw_db:
            return my_list

        ret = mongo_to_dict_helper(my_list)

        if image_type == "random":
            ret['media_list'] = [random.choice(ret['media_list'])]

        return ret


    def populate(self, media_list):
        """ Adds if the user liked or disliked the media """

        for media in media_list:
            m_id = media['media_id']

            if self.is_on_list(m_id, 'list_favs_id'):
                media['favs'] = True

            if self.is_on_list(m_id, 'list_likes_id'):
                media['like'] = True

            if self.is_on_list(m_id, 'list_dislikes_id'):
                media['dislike'] = True

    @staticmethod
    def clean_dict(ret):
        """ Removes the extra information list_< name >_id """
        s = {}
        for key in ret.keys():
            if not key.startswith("list_"):
                continue

            # Remove start "list_" and  "_id"
            s[key[5:-3]] = ret[key]
        return s

    def get_every_media_list(self, username=None):
        if current_user.is_authenticated:
            if not username or username == "me":
                username = current_user.username

            if current_user.username == username:
                ret = mongo_to_dict_helper(self)
                return {'galleries': self.clean_dict(ret)}

        ret = {}
        for key, value in self.__dict__.items():
            if not key.startswith("list_"):
                continue

            my_list = DB_MediaList.objects(pk=value).first()
            if my_list and (my_list.is_public and not my_list.is_unlisted):
                ret[key] = value

        return {'galleries': self.clean_dict(ret)}

    def clear_all(self, username):
        """ Deletes every media list for this object """
        for list_id in self:
            if not self[list_id]:
                continue

            try:
                my_list = DB_MediaList.objects(pk=self[list_id]).first()
                if not my_list:
                    continue

                self[list_id] = None
                if my_list.username != username:
                    print_r(" We can only permanently delete our own collections")
                    continue

            except Exception as e:
                print_exception(e, "Crashed cleaning user data ")

        my_list = DB_MediaList.objects(username=username)
        my_list.delete()

        return {}

    def create(self, username, gallery_name, my_dict):
        my_dict.update({
            "name": gallery_name,
            "username": username,
            "list_type": "gallery",
        })

        # Unlisted galleries are public by default
        if 'is_unlisted' in my_dict and my_dict['is_unlisted']:
            my_dict['is_public'] = True

        my_list = DB_MediaList(**my_dict)
        my_list.save().reload()
        self['list_' + gallery_name + '_id'] = str(my_list.id)

        # Update current user galleries
        if current_user.is_authenticated and current_user.username == username:
            current_user.save(validate=False)

        return my_list

    def update(self, my_dict):
        media_list = self.media_list_get(my_dict['id'], raw_db=True)
        if not media_list:
            return abort(400, "There was a problem updating this media, are you the owner?")

        if not media_list.is_current_user():
            return abort(401, "Unauthorized to access this media resource, please contact the owner")

        # We don't update the name of the list
        if 'name' in my_dict:
            my_dict.pop('name')

        my_dict.pop('id')

        if 'is_public' in my_dict and my_dict['is_public'] != media_list.is_public:
            media_list.set_media_privacy(my_dict['is_public'])

        if 'is_unlisted' in my_dict and my_dict['is_unlisted'] != media_list.is_unlisted:
            media_list.set_media_unlisted(my_dict['is_unlisted'])

        media_list.update(**my_dict)
        media_list.reload()

        ret = mongo_to_dict_helper(media_list)
        return {"galleries": [ret]}

    def set(self, gallery_id, param, value):
        from api.query_helper import get_value_from_text

        if param[0] == "_":
            return abort(401, "Unauthorized access")

        value = get_value_from_text(value)

        # Clean the name so we don't get mongo injections on parameters by removing extra characters and double __
        param = self.get_safe_gallery_name(param)

        print_b(gallery_id + " SET " + param + "=[" + str(value) + "]")
        return self.update({'id': gallery_id, param: value})

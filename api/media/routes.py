import io
import os
import time
import ffmpeg
import datetime
import validators

from api.media import blueprint
from api.api_redis import api_rq

from api import get_response_formatted, get_response_error_formatted, api_key_or_login_required, api_key_login_or_anonymous, cache, sanitizer
from flask import jsonify, request, send_file, redirect

from flask import current_app, url_for, abort
from api.print_helper import *

from api.tools import generate_file_md5, ensure_dir, is_api_call
from api.user.routes import generate_random_user
from .models import File_Tracking

from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q

from wand.image import Image

from flask_cachecontrol import (cache, cache_for, dont_cache, Always, ResponseIsSuccessfulOrRedirect)


def get_media_valid_extension(file_name):
    """ Checks with the system to see if the extension provided is valid,
        You should never trust the frontend """

    extension = os.path.splitext(file_name)[1].upper()
    image_list = [".JPEG", ".JPG", ".GIF", ".GIFV", ".PNG", ".BMP", ".TGA", ".WEBP", ".MP4"]
    if extension not in image_list:
        return False

    return extension


def api_internal_add_to_media_list(media_list, my_file):
    if not media_list:
        return

    # Try to append this media to the media list
    try:
        if media_list['is_public']:
            my_file.update(**{'is_public': True})

        media_list.add_to_list(str(my_file.id))
    except Exception as e:
        print_exception(e, "Failed adding to list, please continue")


def api_internal_upload_media():
    from flask_login import current_user  # Required by pytest, otherwise client crashes on CI
    from api.user.routes import api_actions_on_list

    if request.method != "POST":
        return get_response_error_formatted(404, {"error_msg": "No files to upload!"})

    media_path = File_Tracking.get_media_path()

    # If we don't have an user, we generate a temporal one with random names
    if not current_user.is_authenticated:
        current_user = generate_random_user()

    print(" User to upload files " + current_user.username)

    # Target gallery to upload this file on the user.
    # Media can go to their photostream or to a target gallery.
    # If the target gallery is public, the media will be public too.
    # If the user is anonymous, we also check if the user created the library with "allow anonymous" permission.
    # This should be handled by the media list itself.
    gallery_id = request.args.get("gallery_id", '')
    media_list = current_user.get_media_list(gallery_id, raw_db=True)

    uploaded_ft = []
    for key, f_request in request.files.items():
        print(" Upload multiple " + key)

        user_space_path = current_user.username + "/"
        full_path = media_path + user_space_path
        print(" Save at " + full_path)
        ensure_dir(full_path)

        mime = f_request.mimetype.split('/')[0]
        if mime in ['image', 'video']:
            key = mime
        else:
            if key.startswith('image'): key = "image"
            if key.startswith('video'): key = "video"

        if key in ["image", "video"]:
            file_name = f_request.filename

            md5, size = generate_file_md5(f_request)
            if size == 0:
                return get_response_error_formatted(400, {"error_msg": "THERE WAS SOME PROBLEM WITH UPLOAD!"})

            extension = get_media_valid_extension(file_name)
            if not extension:
                return get_response_error_formatted(400, {"error_msg": "FILE FORMAT NOT SUPPORTED YET!"})

            relative_file_path = user_space_path + md5 + extension
            final_absolute_path = media_path + relative_file_path

            if os.path.exists(final_absolute_path):
                # File already exists on disk, we just ignore it

                my_file = File_Tracking.objects(file_path=relative_file_path).first()

                # A path is defined by the MD5, if there is a duplicate, it is either a collision or someone playing with
                # this file / user. We could check if the user has changed, but the plan is to let users upgrade from
                # anonymous into real users, and we might not want to move the final file.

                # Eventually if the project grows, files in folders like this are not ideal and all this code should get revamped

                if my_file:
                    print(" FILE ALREADY UPLOADED WITH ID " + str(my_file.id))

                    ret = my_file.serialize()
                    ret['is_duplicated'] = True

                    uploaded_ft.append(ret)
                    api_internal_add_to_media_list(media_list, my_file)
                    continue

                print(" FILE WAS LOST - CREATE NEW")

            info = {}

            if key == "image":
                try:
                    image = Image(file=f_request)

                    print(" Image orientation " + str(image.orientation))
                    # Image is rotated internally, we have to invert our dimensions
                    if image.orientation in ['right_top', 'top_right', 'right_bottom', 'bottom_right']:
                        print(" Rotate Image ")
                        info['width'] = image.height
                        info['height'] = image.width
                    else:
                        info['width'] = image.width
                        info['height'] = image.height

                    # Rest request seek pointer to start so we can save it after validation
                    f_request.seek(0)
                    f_request.save(final_absolute_path)

                except Exception as e:
                    print(" CRASH on loading image " + str(e))
                    return get_response_error_formatted(400, {"error_msg": "Image is not in a valid format!"})

            if key == "video":
                try:
                    thumb_time = 1

                    f_request.save(final_absolute_path)
                    probe = ffmpeg.probe(final_absolute_path)

                    video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'),
                                        None)
                    width = info['width'] = int(video_stream['width'])
                    height = info['height'] = int(video_stream['height'])
                    duration = info['duration'] = float(video_stream['duration'])

                    target_path = final_absolute_path + ".PREVIEW.PNG"

                    thumb_time = duration / 3

                    if os.path.exists(target_path):
                        os.remove(target_path)

                    ffmpeg.input(final_absolute_path, ss=thumb_time).filter('scale', width, -1).output(target_path,
                                                                                                       vframes=1).run()

                except Exception as e:
                    print(" CRASH on loading image " + str(e))
                    os.remove(final_absolute_path)
                    return get_response_error_formatted(400, {"error_msg": "Image is not in a valid format!"})

            new_file = {
                'info': info,
                'file_name': file_name,
                'file_path': relative_file_path,
                'file_type': key,
                'file_size': size,
                'file_format': extension,
                'checksum_md5': md5,
                'username': current_user.username,
                'is_anon': current_user.is_anon,

                # An user file by default is not public, but if you are anonymous, the file is public
                'is_public': current_user.is_anon or current_user.is_media_public
            }

            my_file = File_Tracking(**new_file)
            my_file.save()

            api_internal_add_to_media_list(media_list, my_file)

            new_file['media_id'] = str(my_file.id)
            uploaded_ft.append(new_file)

    ret = {'media': uploaded_ft, 'username': current_user.username, 'status': 'success'}
    return get_response_formatted(ret)


@blueprint.route('/update', methods=['POST'])
@api_key_or_login_required
def api_update_a_media():
    """ Updates the media data which starts with my_
    ---
    tags:
      - user
    schemes: ['http', 'https']
    deprecated: false
    definitions:
      user_file:
        type: object
    responses:
      200:
        description: Returns the updated media
      401:
        description: User cannot update this media
    """
    from flask_login import current_user  # Required by pytest, otherwise client crashes on CI
    from api.media.models import File_Tracking

    json = request.json
    if not current_user.is_authenticated:
        return abort(404, "User is not valid")

    my_file = File_Tracking.objects(pk=json['media_id']).first()
    if not my_file:
        return abort(404, "Media is not valid")

    ret = my_file.update_with_checks(json)
    if not ret:
        return abort(400, "You cannot edit this library")

    ret['username'] = current_user.username

    return get_response_formatted(ret)


@blueprint.route('/upload_from_web', methods=['POST'])
def api_web_upload_media():
    """ Uploads without an user or without checking a token, we use this to create new users on the fly """
    return api_internal_upload_media()


@blueprint.route('/upload', methods=['POST'])
@api_key_login_or_anonymous
def api_upload_media():
    """Upload media files to this system
    ---
    tags:
      - media
    schemes: ['http', 'https']
    deprecated: false
    definitions:
      image_file:
        type: object
    parameters:
        - in: query
          name: key
          schema:
            type: string
          description: A token that you get when you register or when you ask for a token
    responses:
      200:
        description: Returns if the file was successfully uploaded
        schema:
          id: Standard status message
          type: object
          properties:
            msg:
                type: string
            status:
                type: string
            timestamp:
                type: string
            time:
                type: integer

    """
    return api_internal_upload_media()


def api_dynamic_conversion(my_file, abs_path, relative_path, extension, thumbnail, filename, cache_file=True):
    """ Converts the file dynamically into an extension, and saves the file if it was requested

        The user can append an extension to convert into example .GIF
        The user can append also request it as a image resized thumbnail to be generated .v<PIXEL SIZE>

        The file can be cached or not.
    """
    attachment_filename = filename

    if not extension:
        extension = "PNG"

    if thumbnail:
        try:
            # Our thumbnails adjust to ratio, we can specify
            # It might start with V or H

            if thumbnail[0] in ['v', 'h']:
                orientation = thumbnail[0]
                thumbnail = int(thumbnail[1:])
            else:
                orientation = 'h'
                thumbnail = int(thumbnail)
        except:
            thumbnail = None
            print(thumbnail + " Not a valid thumbnail definition")

    extra = ".CACHE"
    if thumbnail: extra += "." + str(thumbnail)
    if extension: extra += "." + extension

    final_path = abs_path + extra
    if cache_file and os.path.exists(final_path):
        if request.args.get('no_redirect'):
            return send_file(final_path, attachment_filename=attachment_filename + extra)

        return redirect("/static/MEDIA_FILES/" + relative_path + extra)

    try:
        bit_image = io.BytesIO()
        with Image(filename=abs_path) as img:
            if thumbnail:
                aspect_ratio = img.height / img.width
                if orientation == 'v':
                    img.resize(int(thumbnail / aspect_ratio), thumbnail)
                else:
                    img.resize(thumbnail, int(thumbnail * aspect_ratio))

            img.format = extension

            if cache_file:
                # Crop the images to the first
                if len(img.sequence) > 0:
                    img = Image(image=img.sequence[0])

                img.save(filename=final_path)

        if request.args.get('no_redirect'):
            img.save(file=bit_image)
            bit_image.seek(0)
            return send_file(bit_image,
                            mimetype='image/' + extension,
                            as_attachment=True,
                            attachment_filename=attachment_filename + extra)

    except Exception as exc:
        print_exception(exc, "CRASH")
        return get_response_error_formatted(500, {"error_msg": "Failed to convert to format " + extension})

    print_b(" SERVE " + relative_path + extra)
    return redirect("/static/MEDIA_FILES/" + relative_path + extra)


@blueprint.route('/category/<string:media_category>', methods=['GET'])
@api_key_login_or_anonymous
def api_fetch_media_with_media_category(media_category):
    """Returns a list of media objects to display.

    This API is only for public media
    ---
    tags:
      - media
    schemes: ['http', 'https']
    deprecated: false
    definitions:
      image_file:
        type: object
    parameters:
        - in: query
          name: media_category
          schema:
            type: string
          description: Just specify from the list of media categories
    responses:
      200:
        description: Returns a list of media files
      401:
        description: User doesn't have access to this resource.
      404:
        description: Category doesn't exist anymore on the system

    """
    from flask_login import current_user  # Required by pytest, otherwise client crashes on CI
    from api.media.models import File_Tracking

    DEFAULT_ITEMS_LIMIT = 25
    items = int(request.args.get('items', DEFAULT_ITEMS_LIMIT))
    page = int(request.args.get('page', 0))
    offset = page * items

    query = Q(is_public=True)

    if media_category != "NEW":
        query = query & Q(tags__contains=media_category)

    print_h1(" LOAD PAGE " + str(page))

    op = File_Tracking.objects(query)

    if request.args.get('order', 'desc') == 'desc':
        op = op.order_by('-creation_date')
    else:
        op = op.order_by('+creation_date')

    files = op.skip(offset).limit(items)

    return_list = []

    count = 0
    for f in files:
        if f.exists():
            return_list.append(f.serialize())
            count += 1

            # We should limit this on the File_Tracking call
            if count > 150:
                break

    if current_user.is_authenticated:
        current_user.populate_media(return_list)

    ret = {'status': 'success', 'media_files': return_list, 'items': items, 'offset': offset, 'page': page}
    return get_response_formatted(ret)


@blueprint.route('/get/<string:media_id>', methods=['GET'])
@api_key_login_or_anonymous
@cache_for(hours=48, only_if=ResponseIsSuccessfulOrRedirect)
def api_get_media(media_id, image_only=False):
    """Returns a media object given it's media_id.
        The user might be rejected if the media is private
        The user can specify an extension to the media_id file and it will be converted on the fly
    ---
    tags:
      - media
    schemes: ['http', 'https']
    deprecated: false
    definitions:
      image_file:
        type: object
    parameters:
        - in: query
          name: thumbnail
          schema:
            type: string
          description: You can specify a Thumbnail size that will correct the aspect ratio Examples .v256.PNG or .h128.GIF
        - in: query
          name: extension
          schema:
            type: string
          description: Extend the URL with a valid extension and it will convert on the fly for you without going through the RQ Examples .PNG .GIF
        - in: query
          name: key
          schema:
            type: string
          description: A token that you get when you register or when you ask for a token

    responses:
      200:
        description: Returns a file or a generic placeholder for the file
      401:
        description: User doesn't have access to this resource.
      404:
        description: File doesn't exist anymore on the system

    """
    from flask_login import current_user  # Required by pytest, otherwise client crashes on CI

    username = None
    if current_user.is_authenticated:
        username = current_user.username

    print_b(" SERVE " + media_id)

    arr = media_id.split(".")
    media_id = arr[0]

    extension = arr[-1] if len(arr) > 1 else None
    #if extension: print(" CONVERSION REQUEST " + extension)

    thumbnail = arr[-2] if len(arr) > 2 else None
    #if thumbnail: print(" THUMBNAIL REQUEST " + thumbnail)

    my_file = File_Tracking.objects(pk=media_id).first()
    if not my_file:
        if is_api_call():
            return get_response_error_formatted(404, {"error_msg": "FILE NOT FOUND"})
        else:
            return redirect("/static/img-api/images/placeholder.jpg")

    if not my_file.is_public and my_file.username != username:
        if is_api_call():
            return get_response_error_formatted(401, {"error_msg": "FILE IS PRIVATE!"})
        else:
            return redirect("/static/img-api/images/placeholder_private.jpg")

    relative_path = my_file.file_path
    abs_path = File_Tracking.get_media_path()

    if image_only and my_file.file_type == "video":
        extension = "PNG"
        thumbnail = "v512"

    if extension or thumbnail:
        # If it is a video we want to use the video preview
        if my_file.file_type == "video":
            relative_path += ".PREVIEW.PNG"

        return api_dynamic_conversion(my_file, abs_path + relative_path, relative_path, extension, thumbnail,
                                      my_file.file_name, True)

    if request.args.get('no_redirect'):
        return send_file(abs_path + relative_path, attachment_filename=my_file.file_name)

    return redirect("/static/MEDIA_FILES/" + relative_path)


@blueprint.route('/get_image/<string:media_id>', methods=['GET'])
@api_key_login_or_anonymous
@cache_for(hours=48, only_if=ResponseIsSuccessfulOrRedirect)
def api_get_media_image(media_id):
    """Returns a media object given it's media_id, if it is a video, it will transform it into an image.
        Check /get for a full description
    ---
    tags:
      - media
    schemes: ['http', 'https']
    deprecated: false
    definitions:
      image_file:
        type: object

    """

    return api_get_media(media_id, image_only=True)


@blueprint.route('/stream/<string:user_id>', methods=['GET'])
def api_get_user_photostream(user_id):
    """Returns a json object with a list of media objects owned by this user.
    ---
    tags:
      - media
    schemes: ['http', 'https']
    deprecated: false
    definitions:
      image_file:
        type: object
    parameters:
        - in: query
          name: key
          schema:
            type: string
          description: A token that you get when you register or when you ask for a token
    responses:
      200:
        description: Returns a json list of public images or public and private if it is yourself
        schema:
          id: Media list
          type: object
          properties:
            media_files:
              type: array
              items:
                type: object
                properties:
                  filename:
                      type: string
                  media_id:
                      type: string
                  username:
                      type: string
                  is_public:
                      type: boolean
    """
    from flask_login import current_user  # Required by pytest, otherwise client crashes on CI

    username = None
    if current_user.is_authenticated:
        username = current_user.username

    if user_id == username:
        query = Q(username=username)
    else:
        query = Q(username=user_id) & Q(is_public=True)

    op = File_Tracking.objects(query)

    if request.args.get('order', 'desc') == 'desc':
        op = op.order_by('-creation_date')
    else:
        op = op.order_by('+creation_date')

    DEFAULT_ITEMS_LIMIT = 25
    items = int(request.args.get('items', DEFAULT_ITEMS_LIMIT))
    page = int(request.args.get('page', 0))
    offset = page * items

    print_h1(" LOAD PAGE " + str(page))
    file_list = op.skip(offset).limit(items)

    return_list = []
    for ft in file_list:
        return_list.append(ft.serialize())

    ret = {'status': 'success', 'items': items, 'offset': offset, 'page': page}

    if current_user.is_authenticated:
        current_user.populate_media(return_list)

        cover_id = current_user.get_cover()
        background_id = current_user.get_background()

        if cover_id: ret['cover_id'] = cover_id
        if background_id: ret['background_id'] = background_id

    ret['media_files'] = return_list

    return get_response_formatted(ret)


def api_populate_media_list(user_id, media_list, is_order_asc=True):
    """ Populates a list of media, checking that the media is public or the user is itself """
    from flask_login import current_user

    if len(media_list) == 0:
        return {'media_files': []}

    if user_id == "me":
        if not current_user.is_authenticated:
            return abort(404, "User is not valid")

        user_id = current_user.username

    username = None
    if current_user.is_authenticated:
        username = current_user.username

    ####################### PAGINATION ################################################

    DEFAULT_ITEMS_LIMIT = 50
    items = int(request.args.get('items', DEFAULT_ITEMS_LIMIT))
    page = int(request.args.get('page', 0))
    offset = page * items

    query = Q(pk__in=media_list)

    if user_id != username:
        query = query & Q(is_public=True)

    op = File_Tracking.objects(query)

    ######### TODO: ORDER SHOULD BE THE DATE IT GOT ON THE LIBRARY ####################

    if is_order_asc:
        op = op.order_by('-creation_date')
    else:
        op = op.order_by('+creation_date')

    file_list = op.skip(offset).limit(items)

    return_list = [ft.serialize() for ft in file_list]

    if current_user.is_authenticated:
        current_user.populate_media(return_list)

    ret = {'media_files': return_list, 'items': items, 'offset': offset, 'page': page}
    return ret


@blueprint.route('/fetch', methods=[
    'GET',
    'POST',
])
@api_key_login_or_anonymous
def api_fetch_from_url():
    """Returns a JOB ID for the task of fetching this resource. It calls RQ to get the task done.
    ---
    tags:
      - media
    schemes: ['http', 'https']
    deprecated: false
    definitions:
      request_url:
        type: object
    parameters:
        - in: query
          name: request_url
          schema:
            type: string
          description: A valid URL that contains a file format on it.
    responses:
      200:
        description: Returns a job ID
        schema:
          id: Job ID
          type: object
          properties:
            job_id:
              type: string
    """
    from flask_login import current_user  # Required by pytest, otherwise client crashes on CI

    if request.method == 'POST':
        request_url = request.json['request_url']
    else:
        request_url = request.args.get("request_url")

    if not request_url:
        return get_response_error_formatted(404, {"error_msg": "URL Not found"})

    if not validators.url(request_url):
        return get_response_error_formatted(400, {'error_msg': "Please provide a valid URL"})

    # If we don't have an user, we generate a temporal one with random names
    if not current_user.is_authenticated:
        current_user = generate_random_user()

    token = current_user.generate_auth_token()
    api_call = "https://img-api.com/api/media/upload?key=" + token

    json = {
        'request_url': request_url,
        'username': current_user.username,
        'token': token,
        'api_callback': api_call,
    }

    job = api_rq.call("worker.fetch_url_image", json)
    if not job:
        return get_response_error_formatted(401, {'error_msg': "Failed reaching the services."})

    ret = {'status': 'success', 'job_id': job.id, 'request_url': request_url}
    return get_response_formatted(ret)


def api_media_set_privacy(media_id, is_public):
    media_file = File_Tracking.objects(id=media_id).first()
    if not media_file:
        return False

    # We can only change the permission to our current user, and owner of the media
    if not media_file.is_current_user():
        return False

    media_file.update(**{"is_public": is_public})
    return True


def api_get_media_id(media_id):
    media_file = File_Tracking.objects(id=media_id).first()

    if not media_file:
        return abort(404, {'error_msg': "Media not found."})

    if media_file.is_private() and not media_file.is_current_user():
        return abort(403, {'error_msg': "Media is private."})

    print_b(" MEDIA " + media_file.file_name)
    return media_file


@blueprint.route('/posts/<string:media_id>/get', methods=['GET'])
@api_key_login_or_anonymous
def api_get_media_post(media_id):
    """Returns an individual post information
    ---
    tags:
      - media
    schemes: ['http', 'https']
    deprecated: false
    definitions:
      image_file:
        type: object
    parameters:
        - in: query
          name: media_id
          schema:
            type: string
          description: Just a media id
    responses:
      200:
        description: Returns OK if you can set this permission
      403:
        description: Forbidden, user is not the owner of this image
      404:
        description: File Media is missing

    """
    from flask_login import current_user  # Required by pytest, otherwise client crashes on CI

    ret = {'status': 'success', 'media_id': media_id}

    media_file = api_get_media_id(media_id)

    ################ Next and previous ##################

    get_next = request.args.get("next", '')
    get_prev = request.args.get("prev", '')

    position = 0
    media_list = None

    if current_user.is_authenticated:
        user = current_user
    else:
        user = media_file.get_owner()
        if not user:
            return get_response_error_formatted(403, {'error_msg': "User is private."})

    if get_next:
        position = 1
        if (get_next != "posts"):
            media_list = user.get_media_list(get_next, raw_db=True)

    if get_prev:
        position = -1
        if (get_prev != "posts"):
            media_list = user.get_media_list(get_prev, raw_db=True)

    if position != 0:
        if media_list:
            media_file = media_list.get_media_position(media_id, position)
        else:
            media_file = user.get_photostream_position(media_id, position)

    ######################################################

    if not media_file:
        return get_response_error_formatted(404, {'error_msg': "Missing file."})

    return_list = [media_file.serialize()]

    return get_response_formatted({'status': 'success', "media_files": return_list})


@blueprint.route('/posts/<string:media_id>/set_privacy/<string:privacy_mode>', methods=['GET'])
@api_key_or_login_required
def api_set_media_private_posts_json(media_id, privacy_mode):
    """Sets a media privacy mode
    ---
    tags:
      - media
    schemes: ['http', 'https']
    deprecated: false
    definitions:
      image_file:
        type: object
    parameters:
        - in: query
          name: key
          schema:
            type: string
          description: A token that you get when you register or when you ask for a token
    responses:
      200:
        description: Returns OK if you can set this permission
      403:
        description: Forbidden, user is not the owner of this image
      404:
        description: File is missing

    """
    from flask_login import current_user  # Required by pytest, otherwise client crashes on CI

    if not current_user.is_authenticated:
        return get_response_error_formatted(403, {'error_msg': "Anonymous users are not allowed."})

    media_file = File_Tracking.objects(id=media_id).first()

    if not media_file:
        return get_response_error_formatted(404, {'error_msg': "Missing."})

    if media_file.username != current_user.username:
        return get_response_error_formatted(403, {'error_msg': "This user is not allowed to perform this action."})

    if privacy_mode == 'toggle':
        media_file.is_public = not media_file.is_public

    elif privacy_mode == 'private':
        media_file.is_public = False
    else:
        media_file.is_public = True

    media_file.update(**{'is_public': media_file.is_public})

    if media_file.is_public:
        privacy_mode = "public"
    else:
        privacy_mode = "private"

    print_b(" New privacy " + privacy_mode)

    ret = {'status': 'success', 'media_id': media_id, 'privacy_mode': privacy_mode}
    return get_response_formatted(ret)


@blueprint.route('/<string:media_id>/set/<string:my_key>', methods=['GET', 'POST'])
@api_key_or_login_required
def api_set_media_key(media_id, my_key):
    from flask_login import current_user  # Required by pytest, otherwise client crashes on CI

    media_file = File_Tracking.objects(id=media_id).first()

    if not media_file:
        return get_response_error_formatted(404, {'error_msg': "Missing."})

    if not media_file.is_current_user():
        return get_response_error_formatted(403, {'error_msg': "This user is not allowed to perform this action."})

    value = request.args.get("value", None)
    if not value and 'value' in request.json:
        value = request.json['value']

    if value == None:
        return get_response_error_formatted(400, {'error_msg': "Wrong parameters."})

    value = sanitizer.sanitize(value)
    media_file.set_key_value(my_key, value)

    ret = {'status': 'success', 'media_id': media_id, 'media_list': [media_file.serialize()]}
    return get_response_formatted(ret)


@blueprint.route('/remove/<string:media_id>', methods=['GET', 'DELETE'])
def api_remove_self_media(media_id):
    """Removes a media file
    ---
    tags:
      - media
    schemes: ['http', 'https']
    deprecated: false
    definitions:
      image_file:
        type: object
    parameters:
        - in: query
          name: key
          schema:
            type: string
          description: A token that you get when you register or when you ask for a token
    responses:
      200:
        description: Returns OK if you can remove this file and it has been removed
      403:
        description: Forbidden, user is not the owner of this image
      404:
        description: File is missing

    """
    from flask_login import current_user  # Required by pytest, otherwise client crashes on CI

    if not current_user.is_authenticated:
        return get_response_error_formatted(403, {'error_msg': "Anonymous users are not allowed."})

    media_file = File_Tracking.objects(id=media_id).first()

    if not media_file:
        return get_response_error_formatted(404, {'error_msg': "Missing."})

    if media_file.username != current_user.username:
        return get_response_error_formatted(403, {'error_msg': "This user is not allowed to perform this."})

    media_file.delete()

    ret = {'status': 'success', 'media_id': media_id, 'deleted': True}
    return get_response_formatted(ret)

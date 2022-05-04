import io
import os
import time
import ffmpeg
import datetime
import validators

from api.media import blueprint
from api.api_redis import api_rq

from api import get_response_formatted, get_response_error_formatted, api_key_or_login_required, api_key_login_or_anonymous
from flask import jsonify, request, send_file, redirect

from flask import current_app, url_for, abort

from api.tools import generate_file_md5, ensure_dir, is_api_call
from api.user.routes import generate_random_user
from .models import File_Tracking

from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q

from wand.image import Image


def get_media_valid_extension(file_name):
    """ Checks with the system to see if the extension provided is valid,
        You should never trust the frontend """

    extension = os.path.splitext(file_name)[1].upper()
    image_list = [".JPEG", ".JPG", ".GIF", ".GIFV", ".PNG", ".BMP", ".TGA", ".WEBP", ".MP4"]
    if extension not in image_list:
        return False

    return extension


def api_internal_upload_media():
    from flask_login import current_user, login_user

    if request.method != "POST":
        return get_response_error_formatted(404, {"error_msg": "No files to upload!"})

    media_path = File_Tracking.get_media_path()

    # If we don't have an user, we generate a temporal one with random names
    if not hasattr(current_user, 'username'):
        current_user = generate_random_user()

    print(" User to upload files " + current_user.username)

    uploaded_ft = []
    for key, f_request in request.files.items():
        print(" Upload multiple " + key)

        user_space_path = current_user.username + "/"
        full_path = media_path + user_space_path
        ensure_dir(full_path)

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
                    uploaded_ft.append(my_file.serialize())
                    continue

                print(" FILE WAS LOST - CREATE NEW")

            info = {}

            if key == "image":
                try:
                    image = Image(file=f_request)
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

                    video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
                    width = info['width'] = int(video_stream['width'])
                    height = info['height'] = int(video_stream['height'])
                    duration = info['duration'] = float(video_stream['duration'])

                    target_path = final_absolute_path + ".PREVIEW.PNG"

                    thumb_time = duration / 3

                    if os.path.exists(target_path):
                        os.remove(target_path)

                    ffmpeg.input(final_absolute_path, ss=thumb_time).filter('scale', width, -1).output(target_path, vframes=1).run()

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
                'is_public': current_user.is_anon
            }

            my_file = File_Tracking(**new_file)
            my_file.save()

            new_file['media_id'] = str(my_file.id)
            uploaded_ft.append(new_file)

    ret = {'media': uploaded_ft, 'username': current_user.username, 'status': 'success'}
    return get_response_formatted(ret)


@blueprint.route('/upload_from_web', methods=['POST'])
def api_web_upload_media():
    """ Uploads without an user or without checking a token, we use this to create new users on the fly """
    return api_internal_upload_media()


@blueprint.route('/upload', methods=['POST'])
@api_key_or_login_required
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


def api_dynamic_conversion(my_file, abs_path, extension, thumbnail, filename, cache_file=True):
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

    extra = ""
    if thumbnail: extra += "." + str(thumbnail)
    if extension: extra += "." + extension

    final_path = abs_path + extra
    if cache_file and os.path.exists(final_path):
        return send_file(final_path, attachment_filename=attachment_filename + extra)

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
            img.save(file=bit_image)
            bit_image.seek(0)

            if cache_file:
                img.save(filename=final_path)

    except Exception as exc:
        return get_response_error_formatted(500, {"error_msg": "Failed to convert to format " + extension})

    return send_file(bit_image,
                     mimetype='image/' + extension,
                     as_attachment=True,
                     attachment_filename=attachment_filename + extra)

@blueprint.route('/get/<string:media_id>', methods=['GET'])
@api_key_login_or_anonymous
def api_get_media(media_id):
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
    from flask_login import current_user, login_user

    username = None
    if hasattr(current_user, "username"):
        username = current_user.username

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
            return redirect("/static/images/placeholder.jpg")

    if not my_file.is_public and my_file.username != username:
        if is_api_call():
            return get_response_error_formatted(401, {"error_msg": "FILE IS PRIVATE!"})
        else:
            return redirect("/static/images/placeholder_private.jpg")

    abs_path = File_Tracking.get_media_path() + my_file.file_path

    if extension or thumbnail:
        # If it is a video we want to use the video preview
        if my_file.file_type == "video":
            abs_path += ".PREVIEW.PNG"

        return api_dynamic_conversion(my_file, abs_path, extension, thumbnail, my_file.file_name, True)

    return send_file(abs_path, attachment_filename=my_file.file_name)


@blueprint.route('/posts/<string:user_id>', methods=['GET'])
def api_get_posts_json(user_id):
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
    from flask_login import current_user, login_user

    username = None
    if hasattr(current_user, "username"):
        username = current_user.username

    if user_id == username:
        query = Q(username=username)
    else:
        query = Q(username=user_id) & Q(is_public=True)

    file_list = File_Tracking.objects(query)

    return_list = []
    for ft in file_list:
        return_list.append({
            'media_id': str(ft.pk),
            'is_public': ft.is_public,
            'username': str(ft.username),
            'filename': str(ft.file_name),
            'file_format': str(ft.file_format),
            'creation_date': time.mktime(ft.creation_date.timetuple()),
        })

    ret = {'status': 'success', 'media_files': return_list}
    return get_response_formatted(ret)


@blueprint.route('/fetch', methods=[
    'GET',
    'POST',
])
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
    from flask_login import current_user

    if request.method == 'POST':
        request_url = request.json['request_url']
    else:
        request_url = request.args.get("request_url")

    if not request_url:
        return get_response_error_formatted(404, {"error_msg": "URL Not found"})

    if not validators.url(request_url):
        return get_response_error_formatted(400, {'error_msg': "Please provide a valid URL"})

    # If we don't have an user, we generate a temporal one with random names
    if not hasattr(current_user, 'username'):
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


@blueprint.route('/posts/<string:media_id>/set/<string:privacy_mode>', methods=['GET'])
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
    from flask_login import current_user

    if not hasattr(current_user, "username"):
        return get_response_error_formatted(403, {'error_msg': "Anonymous users are not allowed."})

    media_file = File_Tracking.objects(id=media_id).first()

    if not media_file:
        return get_response_error_formatted(404, {'error_msg': "Missing."})

    if media_file.username != current_user.username:
        return get_response_error_formatted(403, {'error_msg': "This user is not allowed to perform this."})

    if privacy_mode == 'private':
        media_file.is_public = False
    else:
        media_file.is_public = True

    media_file.save()

    ret = {'status': 'success', 'media_id': media_id, 'privacy_mode': privacy_mode}
    return get_response_formatted(ret)


@blueprint.route('/remove/<string:media_id>', methods=['GET'])
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
    from flask_login import current_user

    if not hasattr(current_user, "username"):
        return get_response_error_formatted(403, {'error_msg': "Anonymous users are not allowed."})

    media_file = File_Tracking.objects(id=media_id).first()

    if not media_file:
        return get_response_error_formatted(404, {'error_msg': "Missing."})

    if media_file.username != current_user.username:
        return get_response_error_formatted(403, {'error_msg': "This user is not allowed to perform this."})

    media_file.delete()

    ret = {'status': 'success', 'media_id': media_id, 'deleted': True}
    return get_response_formatted(ret)

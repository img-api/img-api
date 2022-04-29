import os
import validators

from api.media import blueprint
from api.api_redis import api_rq

from api import get_response_formatted, get_response_error_formatted, api_key_or_login_required
from flask import jsonify, request, send_file

from flask import current_app, url_for

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
    image_list = [".JPEG", ".JPG", ".GIF", ".GIFV", ".PNG", ".BMP", ".TGA"]
    if extension not in image_list:
        return False

    return extension


def get_media_path():
    media_path = current_app.config.get('MEDIA_PATH')
    if not media_path:
        abort(500, "Internal error, application MEDIA_PATH is not configured!")

    return media_path


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
    from flask_login import current_user, login_user

    if request.method != "POST":
        return get_response_error_formatted(404, {"error_msg": "No files to upload!"})

    media_path = get_media_path()

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

        if key.startswith("image"):
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
                print(" FILE ALREADY UPLOADED ")
                continue

            info = {}
            try:
                image = Image(file=f_request)
                info['width'] = image.width
                info['height'] = image.height

                # Rest request seek pointer to start so we can save it after validation
                f_request.seek(0)

            except Exception as e:
                print(" CRASH on loading image " + str(e))
                return get_response_error_formatted(400, {"error_msg": "Image is not in a valid format!"})

            f_request.save(final_absolute_path)
            uploaded_ft.append({'file_md5': md5})

            new_file = {
                'info': info,
                'file_name': file_name,
                'file_path': relative_file_path,
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

    ret = {'uploaded_files': uploaded_ft, 'username': current_user.username, 'status': 'success'}
    return get_response_formatted(ret)

@blueprint.route('/upload_from_web', methods=['POST'])
def api_web_upload_media():
    """ Uploads without an user or without checking a token, we use this to create new users on the fly """
    return api_upload_media()

@blueprint.route('/get/<string:media_id>', methods=['GET'])
def api_get_media(media_id):
    """Returns a media object given it's media_id.
        The user might be rejected if the media is private
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

    abs_path = get_media_path() + my_file.file_path
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
        query = Q(username=username) | Q(is_public=True)

    file_list = File_Tracking.objects(query)

    return_list = []
    for ft in file_list:
        return_list.append({
            'filename': str(ft.file_name),
            'media_id': str(ft.pk),
            'username': str(ft.username),
            'is_public': ft.is_public
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



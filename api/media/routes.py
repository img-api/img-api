import os

from api.media import blueprint
from api import get_response_formatted, get_response_error_formatted
from flask import jsonify, request

from api.tools import generate_file_md5, ensure_dir
from flask import current_app, url_for
from api.user.routes import generate_random_user


def get_media_valid_extension(file_name):
    """ Checks with the system to see if the extension provided is valid,
        You should never trust the frontend """

    extension = os.path.splitext(file_name)[1].upper()
    image_list = [".JPEG", ".JPG", ".GIF", ".GIFV", ".PNG", ".BMP", ".TGA"]
    if extension not in image_list:
        return False

    return extension


@blueprint.route('/upload', methods=['POST'])
def api_upload_media():
    from flask_login import current_user, login_user
    """Upload media files to this system
    ---
    tags:
      - test
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
    from .models import File_Tracking

    if request.method != "POST":
        return get_response_error_formatted(404, {"error_msg": "No files to upload!"})

    media_path = current_app.config.get('MEDIA_PATH')
    if not media_path:
        return get_response_error_formatted(500,
                                            {"error_msg": "Internal error, application MEDIA_PATH is not configured!"})

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

            f_request.save(final_absolute_path)
            uploaded_ft.append({'file_md5': md5})

            new_file = {
                'file_name': file_name,
                'file_path': relative_file_path,
                'file_size': size,
                'file_format': extension,
                'checksum_md5': md5,
                'username': current_user.username,
                'is_public': current_user.is_anon
            }

            my_file = File_Tracking(**new_file)
            my_file.save()

    ret = {'uploaded_files': uploaded_ft, 'username': current_user.username, 'status': 'success'}
    return get_response_formatted(ret)
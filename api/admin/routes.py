import os
from datetime import datetime

import bcrypt
import ffmpeg
from api import (admin_login_required, api_key_login_or_anonymous,
                 api_key_or_login_required, cache,
                 get_response_error_formatted, get_response_formatted)
from api.admin import blueprint
from api.media.models import File_Tracking
from api.print_helper import *
from flask import current_app, url_for


def has_no_empty_params(rule):
    defaults = rule.defaults if rule.defaults is not None else ()
    arguments = rule.arguments if rule.arguments is not None else ()
    return len(defaults) >= len(arguments)


@blueprint.route('/', methods=['GET', 'POST'])
def api_admin_hello_world():
    """
        Returns a simple hello world used by the testing unit to check if the system works
    """

    return get_response_formatted({'status': 'success', 'msg': 'Admin success'})


@blueprint.route('/service', methods=['GET', 'POST'])
@api_key_or_login_required
@admin_login_required
def api_admin_get_service_token():
    """
        Returns a token for a service user that has no login and it is read only
    """
    from api.user.models import User
    from api.user.routes import generate_random_name

    user = User.objects(username="service").first()

    if not user:
        password = generate_random_name() + str(datetime.now())
        user_obj = {
            'password': bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).hex(),
            'username': "service",
            'email': "service@img-api.com",
            'is_anon': True,
            'is_readonly': True,
            'active': True,
        }

        user = User(**user_obj)
        user.save()

    token = user.generate_auth_token()
    return get_response_formatted({'status': 'success', 'msg': 'User service', 'token': token})


@blueprint.route("/site-map")
@api_key_or_login_required
@admin_login_required
def site_map():
    """Returns a view of the site map for debugging.
    ---
    tags:
      - test
    schemes: ['http', 'https']
    deprecated: false
    definitions:
      site_map:
        type: object
    responses:
      200:
        description: Will return a list of entry points and function paths
        schema:
          id: url map definitions
          type: object
          properties:
            site_map:
              type: array
              items:
                type: object
                properties:
                  url_path:
                      type: string
                  entry_path:
                      type: string

    """

    links = []
    for rule in current_app.url_map.iter_rules():
        # Filter out rules we can't navigate to in a browser
        # and rules that require parameters
        if "GET" in rule.methods and has_no_empty_params(rule):
            url = url_for(rule.endpoint, **(rule.defaults or {}))
            links.append((url, rule.endpoint))

    # links is now a list of url, endpoint tuples
    return get_response_formatted({'status': "success", 'site_map': links})


def reindex_disk_file(username, checksum_md5, file_name, extension, relative_path, absolute_path):
    from wand.image import Image

    key = None
    if File_Tracking.is_extension_image(extension):
        key = "image"

    if File_Tracking.is_extension_video(extension):
        key = "video"

    if not key:
        return

    size = os.path.getsize(absolute_path)
    if size == 0:
        return

    info = {}

    if key == "image":
        image = Image(filename=absolute_path)

        print(" Image orientation " + str(image.orientation))
        # Image is rotated internally, we have to invert our dimensions
        if image.orientation in ['right_top', 'top_right', 'right_bottom', 'bottom_right']:
            print(" Rotate Image ")
            info['width'] = image.height
            info['height'] = image.width
        else:
            info['width'] = image.width
            info['height'] = image.height

    if key == "video":
        probe = ffmpeg.probe(absolute_path)
        video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        info['width'] = int(video_stream['width'])
        info['height'] = int(video_stream['height'])
        info['duration'] = float(video_stream['duration'])

    new_file = {
        'info': info,
        'file_name': file_name,
        'file_path': relative_path,
        'file_type': key,
        'file_size': size,
        'file_format': "." + extension,
        'checksum_md5': checksum_md5,
        'username': username,
        'is_anon': False,
        'is_public': True
    }

    my_file = File_Tracking(**new_file)
    my_file.save()


@blueprint.route('/reindex', methods=['GET', 'DELETE'])
def api_disaster_recovery():
    from flask_login import \
        current_user  # Required by pytest, otherwise client crashes on CI

    if not current_user.is_authenticated:
        return get_response_error_formatted(403, {'error_msg': "Anonymous users are not allowed."})

    if current_user.username != "sergioamr":
        return get_response_error_formatted(403, {'error_msg': "This user is not allowed to perform this."})

    path = current_app.config['MEDIA_PATH']
    l = len(path)

    last_check = ""
    for root, dirs, files in os.walk(path):
        for file in files:
            file_path = os.path.join(root, file)[l:]
            arr = file_path.split("/")

            if len(arr) == 1:
                continue

            username = arr[0]
            if username in ['oinktv']:
                continue

            media_file = arr[1]

            if ".PREVIEW" not in media_file:
                continue

            marr = media_file.split(".")

            md5 = marr[0]
            extension = marr[1]
            file_name = md5 + "." + extension

            relative_path = username + "/" + file_name
            #print_b("MEDIA [" + relative_path + "] ")

            if last_check == relative_path:
                continue

            last_check = relative_path

            media_file = File_Tracking.objects(file_path=relative_path).first()

            if media_file:
                #print_b("FILE OK [" + username + "] " + relative_path)
                continue

            print_r("FILE LOST [" + username + "] " + relative_path)

            abs_path = os.path.join(root, file_name)
            try:
                reindex_disk_file(username, md5, file_name, extension, relative_path, abs_path)
            except Exception as e:
                print_exception(e, "Crash")

    ret = {'status': 'success'}
    return get_response_formatted(ret)

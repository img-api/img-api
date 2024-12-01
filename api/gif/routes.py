import binascii
import io
import random
import re
import time
from datetime import datetime
from io import BytesIO
from urllib.parse import urlparse

import bcrypt
import ffmpeg
import qrcode
import requests
import validators
from api import (admin_login_required, api_key_login_or_anonymous,
                 api_key_or_login_required, cache,
                 get_response_error_formatted, get_response_formatted)
from api.gif import blueprint
from api.gif.models import DB_TenorGif
from api.media.models import File_Tracking
from api.print_helper import *
from api.query_helper import (build_query_from_request, mongo_to_dict_helper,
                              validate_and_convert_dates)
from api.tools import ensure_dir, generate_file_md5, is_api_call, to_bytes
from api.tools.validators import get_validated_email
from flask import Response, abort, jsonify, redirect, request, send_file
from flask_login import current_user
from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q


@blueprint.route('/query', methods=['GET', 'POST'])
def api_gif_get_query():
    extra_args = {'username': "GIF"}

    gifs = build_query_from_request(File_Tracking, global_api=True, extra_args=extra_args)

    ret = {'gifs': gifs}
    return get_response_formatted(ret)


def api_internal_gif_upload(f_request, media_info, file_name, file_extension, file_type="video", gif_username="GIF"):
    media_path = File_Tracking.get_media_path()

    print(" User to upload files " + gif_username)

    user_space_path = gif_username + "/"
    full_path = media_path + user_space_path
    print(" Save at " + full_path)
    ensure_dir(full_path)

    md5, size = generate_file_md5(f_request)
    if size == 0:
        return False

    relative_file_path = user_space_path + md5 + file_extension
    final_absolute_path = media_path + relative_file_path

    #if os.path.exists(final_absolute_path):
    # File already exists on disk, we just ignore it
    #return True

    my_file = File_Tracking.objects(file_path=relative_file_path).first()

    # A path is defined by the MD5, if there is a duplicate, it is either a collision or someone playing with
    # this file / user. We could check if the user has changed, but the plan is to let users upgrade from
    # anonymous into real users, and we might not want to move the final file.

    # Eventually if the project grows, files in folders like this are not ideal and all this code should get revamped

    if my_file:
        print(" FILE ALREADY UPLOADED WITH ID " + str(my_file.id))

    if file_type != "video":
        return

    info = {}
    try:
        thumb_time = 1

        with open(final_absolute_path, 'wb') as f:
            f_request.seek(0)
            f.write(f_request.getvalue())

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
        #os.remove(final_absolute_path)
        return False

    file_metadata = {
        'info': info,
        'file_name': file_name,
        'file_path': relative_file_path,
        'file_type': file_type,
        'file_size': size,
        'file_format': file_extension,
        'checksum_md5': md5,
        'username': gif_username,
        'is_public': True,
        'status': "INDEXED",
    }

    file_metadata.update(media_info)

    if my_file:
        my_file.update(**file_metadata)
    else:
        my_file = File_Tracking(**file_metadata)
        my_file.save()

    return file_metadata


def api_capture_tenor_data(raw_data):
    if not 'results' in raw_data:
        return

    results = raw_data['results']
    for raw_gif in results:
        try:
            tenor = DB_TenorGif.objects(external_uuid=raw_gif['id']).first()
            if tenor:
                # Already indexed
                continue

            data = {'status': "WAITING_INDEX", 'tags': raw_gif['tags']}

            # Deduplicate, we move the tags out of the raw data
            del raw_gif['tags']
            data['raw'] = raw_gif
            new_tenor_gif = DB_TenorGif(**data)
            new_tenor_gif.save(validate=False)

        except Exception as e:
            print_exception(e, " CAPTURE TENOR ")


@blueprint.route('/queue_process', methods=['GET', 'POST'])
def api_gif_process_queue():

    try:
        tenor_process = DB_TenorGif.objects(status="WAITING_INDEX").limit(100)

        media_list = []
        for tenor in tenor_process:

            raw = tenor['raw']
            mp4_url = raw['media_formats']['mp4']['url']

            response = requests.get(mp4_url)
            if response.status_code != 200:
                tenor.update(**{'status': 'FAILED FETCHING' + str(response.status_code)})
                return

            parsed_url = urlparse(mp4_url)

            # Extract the file name and extension
            file_name_with_ext = os.path.basename(parsed_url.path)
            file_name, file_extension = os.path.splitext(file_name_with_ext)

            # Create a temporary file to store the gif data
            gif_data = BytesIO(response.content)

            media_info = {
                'my_title': raw['title'],
                'my_description': raw['content_description'],
                'external_uuid': raw['id'],
                'tags': tenor.tags,
            }

            media_list.append(media_info)

            gif_obj = api_internal_gif_upload(gif_data, media_info, file_name, file_extension)

            if not gif_obj:
                tenor.update(**{'status': 'FAILED_PROCESSING'})
            else:
                tenor.update(**{'status': 'INDEXED'})

        return get_response_formatted({'media': [media_list]})

    except Exception as e:
        print_exception(e, " CAPTURE TENOR ")
        tenor.update(**{'status': 'CRASHED', 'exception': e})

        return get_response_formatted({'tenor': tenor, 'error': 'FAILED', 'exception': e})


@blueprint.route('/gif', methods=['GET', 'POST'])
def api_gif_get_from_request():
    """ """
    from .sentiment import get_gif_for_sentiment

    keywords = request.args.get("keywords", "SAD")

    raw_data, gif, format = get_gif_for_sentiment(keywords)

    api_capture_tenor_data(raw_data)

    raw = request.args.get("raw", None)

    if raw:
        ret = {"keywords": keywords, 'url': gif, 'raw': raw_data, 'format': format}
        return get_response_formatted(ret)

    response = requests.get(gif)
    if response.status_code != 200:
        return {"error": "Failed to download the gif"}, 500

    # Create a temporary file to store the gif data
    gif_data = BytesIO(response.content)
    if format == "mp4":
        return send_file(gif_data, mimetype='video/mp4', as_attachment=False, download_name='sentiment.mp4')

    return send_file(gif_data, mimetype='image/gif', as_attachment=False, download_name='sentiment.gif')

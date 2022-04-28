import os

from api.media import blueprint
from api import get_response_formatted, get_response_error_formatted
from flask import jsonify, request

from api.tools import generate_file_md5, ensure_dir

@blueprint.route('/upload', methods=['GET'])
def api_upload_media():
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
    if request.method != "POST":
        return get_response_error_formatted(404, {"error_msg": "No files to upload!"})

    uploaded_ft = []
    for key, f_request in request.files.items():
        print(" Upload multiple " + key)
        full_path = ""

        ensure_dir(full_path)

        if key.startswith("file"):
            file_name = f_request.filename

            md5 = generate_file_md5(f_request)

            absolute_path = "MYPATH/" + md5
            f_request.save(absolute_path)
            uploaded_ft.append({ 'file_md5': md5 })

    ret = {
        'uploaded_files': uploaded_ft
    }
    return get_response_formatted({'status': 'success', 'msg': 'hello world'})
from app.media import blueprint
from api import get_response_formatted, api_key_or_login_required
from flask import render_template


@blueprint.route('/upload', methods=['GET', 'POST'])
def media_main_upload():
    """ Returns the upload HTML site
        - It can fetch an URL usign a service
        - Upload a file by drag and drop and using the API upload call
    """
    return render_template('media_upload.html')


@blueprint.route('/edit/<string:media_id>', methods=['GET'])
def media_edit_by_id(media_id):
    """ Edits this image, it can create a clone of the image if you want to do something extra with it, like a meme or something.
    """
    return render_template('media_edit.html', media_id=media_id)

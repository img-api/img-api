from app.media import blueprint
from api import get_response_formatted, api_key_or_login_required
from flask import render_template


@blueprint.route('/upload', methods=['GET', 'POST'])
def media_main_upload():
    """ Returns the main HTML site """
    return render_template('media_upload.html')
from app.image import blueprint
from api import get_response_formatted, api_key_or_login_required
from flask import render_template

@blueprint.route('/', methods=['GET', 'POST'])
@api_key_or_login_required
def image_main_render():
    """ Returns the main HTML site """
    return render_template('image_upload.html')


@blueprint.route('/<string:user>/', methods=['GET', 'POST'])
@api_key_or_login_required
def image_main_render(username):
    """ Returns the main HTML site """
    return render_template('image_upload.html')
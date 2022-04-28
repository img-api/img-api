from app.user import blueprint
from api import get_response_formatted, api_key_or_login_required
from flask import render_template

@blueprint.route('/<string:username>/', methods=['GET'])
@blueprint.route('/<string:username>/posts', methods=['GET'])
def user_render_posts(username):
    """ Displays the user videos and images """
    return render_template('user_public_media.html', username=username)



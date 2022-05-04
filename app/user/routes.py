from app.user import blueprint
from api import get_response_formatted, api_key_or_login_required
from flask import render_template

from api.media.models import File_Tracking

@blueprint.route('/<string:username>/posts/<string:media_id>', methods=['GET'])
def user_display_only_media(username, media_id):
    """ Displays only one media image """
    media = File_Tracking.objects(pk=media_id).first()
    return render_template('user_simple_media.html', username=username, media=media, media_id=media_id)


@blueprint.route('/<string:username>/', methods=['GET'])
@blueprint.route('/<string:username>/posts', methods=['GET'])
def user_render_posts(username):
    """ Displays the user videos and images """
    return render_template('user_public_media.html', username=username)



from api import api_key_or_login_required, get_response_formatted
from api.actors import blueprint
from api.print_helper import *
from flask import abort, request


@blueprint.route('/update', methods=['POST'])
@api_key_or_login_required
def api_update_a_media():
    """ Updates an actor """

    from flask_login import \
        current_user  # Required by pytest, otherwise client crashes on CI

    json = request.json
    if not current_user.is_authenticated:
        return abort(404, "User is not valid")

    my_file = File_Tracking.objects(pk=json['media_id']).first()
    if not my_file:
        return abort(404, "Media is not valid")

    ret = my_file.update_with_checks(json)
    if not ret:
        return abort(400, "You cannot edit this library")

    ret['username'] = current_user.username

    return get_response_formatted(ret)

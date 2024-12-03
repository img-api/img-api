
from api import get_response_error_formatted, get_response_formatted
from api.channels import blueprint
from api.channels.models import DB_Channel
from api.query_helper import build_query_from_request
from flask import request
from flask_login import current_user


@blueprint.route('/query', methods=['GET', 'POST'])
def api_channel_get_query():
    channel = build_query_from_request(DB_Channel, global_api=True)
    return get_response_formatted({'channel': channel})


@blueprint.route('/create', methods=['GET', 'POST'])
def api_create_channel():
    print("======= CREATE Channel Local =============")

    json = request.json
    channel = DB_Channel(**json)
    channel.save()

    return get_response_formatted(channel)


@blueprint.route('/rm/<string:channel_id>', methods=['GET', 'POST'])
@blueprint.route('/remove/<string:channel_id>', methods=['GET', 'POST'])
def api_remove_a_channel_by_id(channel_id):
    # CHECK API ONLY ADMIN
    if channel_id == "ALL" and current_user.username == "admin":
        DB_Channel.objects().delete()
        return get_response_formatted({'status': "deleted"})

    db_channel = DB_Channel.objects(id=channel_id).first()

    if not db_channel:
        return get_response_error_formatted(404, {'error_msg': "Business not found for the current user"})

    ret = {'status': "deleted", 'channels': [db_channel]}

    db_channel.delete()
    return get_response_formatted(ret)


@blueprint.route('/get/<string:channel_id>', methods=['GET', 'POST'])
def api_get_channel_info(channel_id):
    """ Channel get info """

    if channel_id == "ALL":
        db_channels = DB_Channel.objects()
        return get_response_formatted(db_channels)

    if not db_channels:
        return get_response_error_formatted(404, {'error_msg': "Channels not found"})

    return get_response_formatted({'channels': db_channels})


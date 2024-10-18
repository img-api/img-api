from api import api_key_or_login_required, get_response_formatted
from app.admin import blueprint
from flask import render_template


@blueprint.route('/', methods=['GET'])
def admin_interface():
    return render_template('admin_interface.html')



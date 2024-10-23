from api import api_key_or_login_required, get_response_formatted
from app.admin import blueprint
from flask import render_template


@blueprint.route('/', methods=['GET', 'POST'])
def admin_template():
    """ Admin interface to manage users
    """
    return render_template('admin_template.html')

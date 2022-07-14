from app.setup import blueprint
from api import get_response_formatted, api_key_or_login_required
from flask import render_template

from flask_login import current_user, LoginManager

@blueprint.route('/', methods=['GET'])
@blueprint.route('/curl', methods=['GET'])
def app_setup_curl_example():
    """ Returns the curl setup examples """

    token = "<Please Login for a token>" if not current_user.is_authenticated else current_user.generate_auth_token()
    return render_template('user_curl.html', token=token)


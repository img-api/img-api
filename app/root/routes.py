from app.root import blueprint
from api import get_response_formatted
from flask import render_template

@blueprint.route('/test', methods=['GET', 'POST'])
def root_app_test():
    """ Returns a simple hello world used by the testing unit to check if the system works """

    return get_response_formatted({'status': 'success', 'msg': 'test_app_root'})


@blueprint.route('/', methods=['GET', 'POST'])
def root_main_render():
    """ Returns the main HTML site """
    from api.media.models import File_Tracking

    files = File_Tracking.objects(is_public=True)
    return render_template('index.html', media_files=files)


@blueprint.route('/login', methods=['GET', 'POST'])
def root_login_into_account():
    """ Shows the login and password """
    return render_template('login.html')

@blueprint.route('/create_account', methods=['GET', 'POST'])
def root_create_account():
    """ Shows the login and password """
    return render_template('create_account.html')
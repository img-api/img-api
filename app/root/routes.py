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
    return render_template('index.html')
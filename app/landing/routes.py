from app.landing import blueprint
from flask import render_template
from api import get_response_formatted


@blueprint.route('/test', methods=['GET', 'POST'])
def app_landing_test():
    return get_response_formatted({'status': 'success', 'msg': 'landing'})


@blueprint.route('/html_check', methods=['GET', 'POST'])
def root_main_render():
    """ Returns the main HTML site """
    return render_template('html_check.html')
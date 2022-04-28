from app.landing import blueprint
from api import get_response_formatted

@blueprint.route('/', methods=['GET', 'POST'])
def app_hello_world():
    """ Returns a simple hello world used by the testing unit to check if the system works """

    return get_response_formatted({'status': 'success', 'msg': 'hello world'})


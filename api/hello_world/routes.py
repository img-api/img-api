from api.hello_world import blueprint
from api import get_response_formatted

def has_no_empty_params(rule):
    defaults = rule.defaults if rule.defaults is not None else ()
    arguments = rule.arguments if rule.arguments is not None else ()
    return len(defaults) >= len(arguments)

@blueprint.route('/', methods=['GET', 'POST'])
def api_hello_world():
    """
        Returns a simple hello world used by the testing unit to check if the system works
        ---
        tags:
          - testing
        definitions:
        parameters:
        responses:
          200:
            All good
    """

    return get_response_formatted({'status': 'success', 'msg': 'hello world'})

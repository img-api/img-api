from api.admin import blueprint
from api import get_response_formatted
from flask import current_app, url_for

def has_no_empty_params(rule):
    defaults = rule.defaults if rule.defaults is not None else ()
    arguments = rule.arguments if rule.arguments is not None else ()
    return len(defaults) >= len(arguments)

@blueprint.route('/', methods=['GET', 'POST'])
def api_admin_hello_world():
    """
        Returns a simple hello world used by the testing unit to check if the system works
    """

    return get_response_formatted({'status': 'success', 'msg': 'Admin success'})

@blueprint.route("/site-map")
def site_map():
    links = []
    for rule in current_app.url_map.iter_rules():
        # Filter out rules we can't navigate to in a browser
        # and rules that require parameters
        if "GET" in rule.methods and has_no_empty_params(rule):
            url = url_for(rule.endpoint, **(rule.defaults or {}))
            links.append((url, rule.endpoint))

    # links is now a list of url, endpoint tuples
    return get_response_formatted({'status': "success", 'site_map': links})
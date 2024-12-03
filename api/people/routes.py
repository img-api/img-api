

from api import get_response_formatted
from api.people import blueprint
from api.query_helper import build_query_from_request

from .models import DB_People


@blueprint.route('/query', methods=['GET', 'POST'])
#@api_key_or_login_required
def api_people_get_query():
    """
    Example of queries: https://dev.gputop.com/api/people/query?year_born=1994
    """

    people = build_query_from_request(DB_People, global_api=True)

    ret = {'people': people}
    return get_response_formatted(ret)

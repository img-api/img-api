
from api.media import blueprint


@blueprint.route('/get/<string:category>', methods=['GET'])
def api_get_tags(category):
    """
        Tags are added to galleries, and media

        Tags are classified in categories

    """


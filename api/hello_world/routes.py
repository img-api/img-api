from api.hello_world import blueprint
from api import get_response_formatted
from flask import jsonify

@blueprint.route('/', methods=['GET'])
def api_hello_world():
    """Returns a hello world for testing the API endpoint
    ---
    tags:
      - test
    schemes: ['http', 'https']
    deprecated: false
    definitions:
      hello_world:
        type: object
    responses:
      200:
        description: Returns a valid json with the msg hello world
        schema:
          id: hello world test
          type: object
          properties:
            msg:
                type: string
            status:
                type: string
            timestamp:
                type: string
            time:
                type: integer

    """
    return get_response_formatted({'status': 'success', 'msg': 'hello world'})

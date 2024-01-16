from flask import Blueprint

blueprint = Blueprint('api_hello_world_blueprint',
                      __name__,
                      url_prefix='/api/hello_world',
                      template_folder='templates',
                      static_folder='static')

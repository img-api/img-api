from flask import Blueprint
from flask_cors import CORS

blueprint = Blueprint('api_user_blueprint',
                      __name__,
                      url_prefix='/api/user',
                      template_folder='templates',
                      static_folder='static')

CORS(blueprint)
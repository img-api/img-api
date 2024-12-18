from flask import Blueprint
from flask_cors import CORS

blueprint = Blueprint('api_subscription_blueprint',
                      __name__,
                      url_prefix='/api/subscription',
                      template_folder='templates',
                      static_folder='static')

CORS(blueprint)

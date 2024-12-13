from flask import Blueprint
from flask_cors import CORS

blueprint = Blueprint('api_ai_services_rocess_blueprint',
                      __name__,
                      url_prefix='/api/ai_services',
                      template_folder='templates',
                      static_folder='static')

CORS(blueprint)

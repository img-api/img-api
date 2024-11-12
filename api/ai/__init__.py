from flask import Blueprint
from flask_cors import CORS

blueprint = Blueprint('api_ai_process_blueprint',
                      __name__,
                      url_prefix='/api/ai',
                      template_folder='templates',
                      static_folder='static')

CORS(blueprint)

import os

from flask import Blueprint, current_app
from flask_cors import CORS

blueprint = Blueprint('api_prompts_blueprint',
                      __name__,
                      url_prefix='/api/prompts',
                      template_folder='templates',
                      static_folder='static')

CORS(blueprint)

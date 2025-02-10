import os
from flask import Blueprint
from flask_cors import CORS
from flask import current_app

blueprint = Blueprint('api_emails_income_blueprint',
                      __name__,
                      url_prefix='/api/emails',
                      template_folder='templates',
                      static_folder='static')

CORS(blueprint)

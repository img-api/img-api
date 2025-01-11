from flask import Blueprint

blueprint = Blueprint('api_test_blueprint',
                      __name__,
                      url_prefix='/api/test',
                      template_folder='templates',
                      static_folder='static')

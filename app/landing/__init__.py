from flask import Blueprint

blueprint = Blueprint('app_landing_blueprint',
                      __name__,
                      url_prefix='/landing',
                      template_folder='templates',
                      static_folder='static')

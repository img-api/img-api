from flask import Blueprint

blueprint = Blueprint('app_admin_blueprint',
                      __name__,
                      url_prefix='/admin',
                      template_folder='templates',
                      static_folder='static')

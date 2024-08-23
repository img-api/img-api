from flask import Blueprint

blueprint = Blueprint('app_business_blueprint',
                      __name__,
                      url_prefix='/company',
                      template_folder='templates',
                      static_folder='static')

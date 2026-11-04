from flask import Blueprint

blueprint = Blueprint('api_tags_blueprint',
                      __name__,
                      url_prefix='/api/tags',
                      template_folder='templates',
                      static_folder='static')


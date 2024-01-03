from flask import Blueprint

blueprint = Blueprint('app_media_blueprint',
                      __name__,
                      url_prefix='/media',
                      template_folder='templates',
                      static_folder='static')

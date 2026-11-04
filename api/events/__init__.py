from flask import Blueprint

blueprint = Blueprint('api_events_blueprint',
                      __name__,
                      url_prefix='/api/events',
                      template_folder='templates',
                      static_folder='static')


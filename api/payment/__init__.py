from flask import Blueprint

blueprint = Blueprint('api_payment_blueprint',
                      __name__,
                      url_prefix='/api/payment',
                      template_folder='templates',
                      static_folder='static')

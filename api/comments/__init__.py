import os

from flask import Blueprint, current_app

blueprint = Blueprint('api_comments_blueprint',
                      __name__,
                      url_prefix='/api/comments',
                      template_folder='templates',
                      static_folder='static')



import os
from flask import Blueprint
from flask_cors import CORS
from flask import current_app

blueprint = Blueprint('api_business_news_blueprint',
                      __name__,
                      url_prefix='/api/news',
                      template_folder='templates',
                      static_folder='static')

CORS(blueprint)

def configure_news_media_folder(app):
    """ Gets the media folder path from the environment or uses a local one inside the application """
    from api.tools import ensure_dir

    media_path = os.environ.get("IMGAPI_MEDIA_PATH", "")

    # The media folder SHOULD not be inside the application folder.
    if not media_path:
        media_path = app.root_path + "/DATA/NEWS_FILES/"

        print("!-------------------------------------------------------------!")
        print("  WARNING MEDIA PATH IS NOT BEING DEFINED ")
        print("  PATH: " + media_path)
        print("!-------------------------------------------------------------!")

    app.config['DATA_NEWS_PATH'] = media_path
    ensure_dir(media_path)


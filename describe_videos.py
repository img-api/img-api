""" One pass of video descriptions (see api/media/describe.py). Usage: python describe_videos.py [--dry-run] """
import sys

from imgapi_launcher import app  # the app must load before the api package

from api.media.describe import run

with app.app_context():
    sys.exit(run(dry_run='--dry-run' in sys.argv))

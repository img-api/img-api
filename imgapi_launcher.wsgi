#!/usr/bin/python3
import sys
import os

sys.path.insert(0, "/home/imgapi/img-api/")
sys.path.insert(0, "/home/imgapi/img-api/site-packages")

os.environ["SETTINGS"]="/home/img-api/imgapi_production_settings.cfg"
os.environ["WSGI"]="TRUE"

os.environ["LC_ALL"] = "C.UTF-8"
os.environ["LANG"] = "C.UTF-8"

sys.getfilesystemencoding = lambda: 'C.UTF-8'

activate_this = '/home/imgapi/img-api/.venv/bin/activate_this.py'
with open(activate_this) as file_:
    exec(file_.read(), dict(__file__=activate_this))

print(" STARTING IMG-API ")
from imgapi_launcher import app as application

#!/usr/bin/python3
import sys
import os
import pwd
import mod_wsgi

print("########## Python " + sys.version + " #############")
#print(mod_wsgi.version)

sys.path.insert(0, "/home/imgapi/img-api/")
sys.path.insert(0, "/home/imgapi/img-api/site-packages")

os.environ["SETTINGS"]="/home/img-api/imgapi_production_settings.cfg"
os.environ["WSGI"]="TRUE"

os.environ["LC_ALL"] = "C.UTF-8"
os.environ["LANG"] = "C.UTF-8"

sys.getfilesystemencoding = lambda: 'C.UTF-8'

os.environ["IMGAPI_MEDIA_PATH"] = "/home/imgapi/IMGAPI_DATA"

print(" EXECUTABLE " + sys.executable)
print(" USER " + pwd.getpwuid(os.getuid()).pw_name)
print(" STARTING IMG-API ")

from imgapi_launcher import app as application

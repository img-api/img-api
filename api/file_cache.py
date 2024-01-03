""" Copyright (C) Blue Eight Engineer Ltd - All Rights Reserved
    Unauthorized copying of this file, via any medium is strictly prohibited
    Proprietary and confidential
"""

import hashlib
from functools import wraps
import io
import os
import sys
import pathlib

import traceback

import threading
import time

from datetime import datetime
import logging
import re

from api import get_response_formatted

from flask_login import current_user
from api.tools import ensure_dir
from flask import json, request
from .print_helper import *

def api_file_cache(func):
    """
    Decorator that caches the data on disk, so we don't hammer our slow database.
    """

    def make_cache_key(*args, **kwargs):
        path = request.path
        lang = "EN"

        params = ""
        for item in request.args.items():
            if item[0] in ["no_cache", "q", "break", "debug_cache"]:
                continue

            if len(params) > 0:
                params += "&"

            params += item[0] + "=" + item[1]

        if current_user.is_authenticated:
            key = lang + "/" + current_user.username + "/" + path + "?" + params
        else:
            key = lang + "/anon/" + path + "?" + params

        cache_key = hashlib.md5(key.encode()).hexdigest()
        return cache_key

    def force_disk_read_cache(real_path=None, key=None):
        if request.args.get("no_cache") == "1":
            return None

        if not key:
            key = make_cache_key()

        debug_cache = request.args.get("debug_cache")

        try:
            if current_user.is_authenticated:
                cache_path = "/tmp/cache/" + current_user.username + "/"
            else:
                cache_path = "/tmp/cache/anon/"


            file_path = cache_path + key + ".json"

            cached = pathlib.Path(file_path)
            if not cached.exists():
                print_r("NOCACHE " + file_path)
                return None

            if real_path:
                check = pathlib.Path(real_path)

                if check.stat().st_mtime > cached.stat().st_mtime:
                    s1 = datetime.fromtimestamp(check.stat().st_mtime)
                    s2 = datetime.fromtimestamp(cached.stat().st_mtime)

                    #if debug_cache:
                    #    print_r("CACHE INVALIDATE " + real_path + " " + str(s1) + " => CACHE " + str(s2))
                    return None

            with open(file_path, 'r') as the_file:
                print("======================= CACHE HIT ====================")
                output = json.load(the_file)
                output['cache'] = key
                output['cached'] = True

                if debug_cache:
                    print_b("CACHED " + file_path)

                return output

        except Exception as e:
            print_r("FAILED " + key + " " + str(e))
            pass

        return None

    def force_disc_cache_write(output, key=None):
        try:
            debug_cache = request.args.get("debug_cache", True)

            if current_user.is_authenticated:
                cache_path = "/tmp/cache/" + current_user.username + "/"
            else:
                cache_path = "/tmp/cache/anon/"

            ensure_dir(cache_path)
            if not key:
                key = make_cache_key()

            with open(cache_path + key + ".json", 'w') as the_file:
                the_file.write(json.dumps(output))

            if debug_cache:
                print_b("SAVED " + cache_path + key + ".json")
        except Exception as e:
            pass

        return None

    @wraps(func)
    def decorated_view(*args, **kwargs):

        output = force_disk_read_cache()
        if output:
            return get_response_formatted(output)

        print_r(" NO CACHE HIT ")
        response = func(*args, **kwargs)
        try:
            data = response.json
            if data['status'] != "success":
                return response

            data['cache'] = True
            force_disc_cache_write(data)
        except Exception as e:
            print_exception(e, "FAILED ON API CACHE")

        return response

    return decorated_view

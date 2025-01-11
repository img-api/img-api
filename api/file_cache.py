""" Copyright (C) Blue Eight Engineer Ltd - All Rights Reserved
    Unauthorized copying of this file, via any medium is strictly prohibited
    Proprietary and confidential
"""
import hashlib
import pathlib
import time
from datetime import datetime
from functools import wraps

from flask import Response, json, request
from flask_login import current_user

from api import get_response_formatted
from api.config import is_api_development
from api.print_helper import *
from api.tools import ensure_dir


def api_file_cache(global_api=True, expiration_secs=86400, data_type="json", ignore_dev=False):
    """
    Decorator that caches API responses to disk to reduce database load.
    Allows passing 'global_api' as a parameter to control specific behavior.
    """

    def make_cache_key(global_api):
        """Generate a unique cache key based on the request and user."""
        path = request.path
        lang = "EN"

        # Build query parameters, ignoring certain keys
        params = "&".join(f"{key}={value}" for key, value in request.args.items()
                          if key not in ["key", "no_cache", "q", "break", "debug_cache"])

        # Include user information in the cache key
        if global_api:
            key = f"{lang}/API/{path}?{params}"
        else:
            if current_user.is_authenticated:
                key = f"{lang}/{current_user.username}/{path}?{params}"
            else:
                key = f"{lang}/anon/{path}?{params}"

        return hashlib.md5(key.encode()).hexdigest()

    def read_from_disk_cache(real_path=None, key=None, global_api=False, expiration_secs=86400):
        """Read cached data from disk if available and valid."""
        if request.args.get("no_cache") == "1":
            return None

        key = key or make_cache_key(global_api)
        debug_cache = request.args.get("debug_cache")

        try:
            if global_api:
                cache_path = f"/tmp/cache/API/"
            else:
                cache_path = f"/tmp/cache/{current_user.username if current_user.is_authenticated else 'anon'}/"

            file_path = f"{cache_path}{key}." + data_type

            cached_file = pathlib.Path(file_path)
            if not cached_file.exists():
                if debug_cache:
                    print_r(f"NOCACHE {file_path}")
                return None

            current_timestamp = time.time()
            expire = current_timestamp - expiration_secs

            if cached_file.stat().st_mtime < expire:
                print(f"CACHE Expired {file_path}")
                return None

            if real_path:
                real_file = pathlib.Path(real_path)
                if real_file.stat().st_mtime > cached_file.stat().st_mtime:
                    if debug_cache:
                        print(f"CACHE INVALID {real_path} is newer than {file_path}")
                    return None

            with open(file_path, 'rb') as f:
                if data_type == "json":
                    output = json.load(f)
                    output['cache'] = key
                    output['cached'] = True
                    if debug_cache:
                        print(f"CACHED {file_path}")
                else:
                    return f.read()
                return output

        except Exception as e:
            print(f"FAILED TO READ CACHE {key}: {e}")

        return None

    def write_to_disk_cache(output, content_type, key=None, global_api=False):
        """Write API response data to disk for caching."""
        try:
            debug_cache = request.args.get("debug_cache")

            key = key or make_cache_key(global_api)

            if global_api:
                cache_path = f"/tmp/cache/API/"
            else:
                cache_path = f"/tmp/cache/{current_user.username if current_user.is_authenticated else 'anon'}/"

            ensure_dir(cache_path)

            file_path = f"{cache_path}{key}." + data_type
            if content_type == "json":
                with open(file_path, 'w') as f:
                    json.dump(output, f)
            else:
                with open(file_path, 'wb') as f:
                    f.write(output)

            if debug_cache:
                print(f"SAVED {file_path}")
        except Exception as e:
            print(f"FAILED TO WRITE CACHE {key}: {e}")

    def decorator(func):
        """The actual decorator that wraps the target function."""

        @wraps(func)
        def decorated_view(*args, **kwargs):
            """Wrapper function that adds caching logic."""
            # Handle 'global_api' if passed as a keyword argument

            # Try to load from the cache

            if not (is_api_development() and kwargs.get('ignore_dev', False)):
                output = read_from_disk_cache(global_api=global_api, expiration_secs=expiration_secs)
                if output:
                    if data_type == "xml":
                        return Response(output, mimetype='text/xml')

                    if data_type == "json":
                        return get_response_formatted(output)

                    return Response(output, mimetype=data_type)

            # If no cache, call the original function
            response = func(*args, **kwargs)

            try:
                # We don't trust our developers? Ofc not.
                if 'json' in response.content_type:
                    data = response.json

                    # Don't cache if the system doesn't want us to cache
                    if data.get('no_cache') == '1':
                        return response

                    if data.get('status') != "success":
                        return response

                    data['cache'] = True
                    content_type = "json"
                elif 'xml' in response.content_type:
                    data = response.data
                    content_type = "xml"
                else:
                    data = response.data
                    content_type = "bin"

                write_to_disk_cache(data, data_type, global_api=global_api)
            except Exception as e:
                print(f"FAILED TO CACHE API RESPONSE: {e}")

            return response

        return decorated_view

    return decorator

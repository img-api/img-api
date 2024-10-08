import os
import sys
import hashlib
import traceback

from flask import jsonify, request, json

from datetime import datetime

def file_as_blockiter(afile, blocksize=65536):
    with afile:
        block = afile.read(blocksize)
        while len(block) > 0:
            yield block
            block = afile.read(blocksize)


def hash_bytestr_iter(bytesiter, hasher, ashexstr=False):
    for block in bytesiter:
        hasher.update(block)
    return hasher.hexdigest() if ashexstr else hasher.digest()


def generate_file_md5(file_p):
    """ Returns the MD5 of a file. Our files will be identified by their MD5.
        Although not perfect for large storage due collisions in production.
    """
    try:
        if isinstance(file_p, str):
            absolute_path = file_p
            with open(absolute_path, 'rb') as fp:
                md5 = hash_bytestr_iter(file_as_blockiter(fp), hashlib.md5(), True)
                size = os.path.getsize(absolute_path)
                return md5, size

        md5 = hashlib.md5(file_p.read()).hexdigest()
        size = file_p.tell()
        file_p.seek(0)

        return md5, size

    except Exception as err:
        traceback.print_tb(e.__traceback__)

    return None, None


def ensure_dir(f):
    """Ensure that a needed directory exists, creating it if it doesn't"""

    try:
        d = os.path.dirname(f)
        if not os.path.exists(d):
            os.makedirs(d)

        return os.path.exists(f)
    except OSError:
        if not os.path.isdir(f):
            raise

    return None


def is_api_call():
    """ An api call is defined either by an application/json content header or our api key """
    if request.args.get("key"):
        return True

    if 'Content-Type' in request.headers and request.headers['Content-Type'] == 'application/json':
        return True

    return False


def json_clean(obj):
    """ Returns the same object, but it ignores all the serialization problems """
    return json.loads(json.dumps(obj, default=lambda o: '<not serializable>'))


def get_timestamp():
    d = datetime.now()
    unixtime = time.mktime(d.timetuple())
    return int(unixtime)


def to_bytes(x, charset=sys.getdefaultencoding(), errors='strict'):
    if isinstance(x, int):
        x = str(int)

    if x is None:
        return None
    if isinstance(x, (bytes, bytearray, memoryview)):
        return bytes(x)
    if isinstance(x, str):
        return x.encode(charset, errors)
    raise TypeError('Expected bytes')
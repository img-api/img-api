import os
import redis
from wand.image import Image

# https://www.pythonpool.com/imagemagick-python/

from rq import Worker, Queue, Connection

listen = ['default']

redis_url = os.getenv('REDISTOGO_URL', 'redis://localhost:6379')

conn = redis.from_url(redis_url)


def is_worker_alive(msg):
    print("I AM ALIVE " + msg)
    return msg


def convert_image(json):
    """ Converts into a different format and returns the file path to retrieve the image """

    operation = json['operation']
    image_path = json['media_path']
    target_path = json['target_path']
    transformation = json['transformation']

    if operation == "convert":
        try:
            image = Image(filename=image_path)
            convert = image.convert(transformation)
            convert.save(filename=target_path)
        except Exception as e:
            return "FAILED"

        return "OK"

    return "OK"


if __name__ == '__main__':
    with Connection(conn):
        worker = Worker(list(map(Queue, listen)))
        worker.work()
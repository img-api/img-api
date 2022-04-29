import os
import redis
import datetime

from rq import Queue
from rq.job import Job

class Remote_Task():
    def init(self, app):
        print(" STARTING REDIS CONNECTION ")

        redis_url = os.getenv('REDISTOGO_URL', 'redis://localhost:6379')

        self.conn = redis.from_url(redis_url)
        self.queue = Queue(connection=self.conn)

        job = self.call("worker.is_worker_alive", "IMG-API " + str(datetime.datetime.now()))

    def call(self, transform_name, media_path):
        job = self.queue.enqueue(transform_name, media_path, result_ttl=5000)
        return job

    def fetch_job(self, job_id):
        job = Job.fetch(job_id, connection=self.conn)
        return job

api_rq = Remote_Task()

def init_redis(app):
    api_rq.init(app)



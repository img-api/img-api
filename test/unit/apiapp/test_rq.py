from datetime import datetime
import time

from test.unit.apiapp import client
from api.api_redis import api_rq

def test_rq_jobs(client):
    # If the worker is not connected, it will fail all the tests

    return

    msg = "IMG-API " + str(datetime.now())
    job = api_rq.call("worker.is_worker_alive", msg)

    assert job != None

    # Check that the job has the right length, it is a very long string
    assert len(job.id) == 36

    # Test if we can get a message from the worker in less than 5s
    count = 5
    while job.get_status() != "finished":
        job = api_rq.fetch_job(job.id)
        if job.get_status() == "finished":
            break

        time.sleep(1)
        count -= 1

    assert count > 0
    assert job.result == msg




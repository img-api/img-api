import json

from test.unit.apiapp import client

def test_hello_world(client):
    ret = client.get("/api/hello_world/")

    assert ret.json['status'] == 'success'
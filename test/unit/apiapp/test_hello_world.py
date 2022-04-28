from test.unit.apiapp import client

def test_hello_world(client):
    json = client.get("/api/hello_world/")

    assert True
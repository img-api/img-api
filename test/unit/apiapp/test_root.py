from test.unit.apiapp import client

def test_landing(client):
    landing = client.get("/landing/html_check")
    html = landing.data.decode()

    # Spot check important text
    assert "Landing check" in html
    assert landing.status_code == 200

def test_hello_world(client):
    landing = client.get("/")

    json = client.get("/hello_world/")

    assert True
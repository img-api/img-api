from test.unit.apiapp import client

def test_landing(client):
    landing = client.get("/")
    html = landing.data.decode()

    # Check that links to `about` and `login` pages exist
    assert "<a href=\"/about/\">About</a>" in html
    assert " <a href=\"/home/\">Login</a>" in html

    # Spot check important text
    assert "Landing test." in html
    assert landing.status_code == 200

def test_hello_world(client):
    landing = client.get("/")

    json = client.get("/hello_world/")

    assert True
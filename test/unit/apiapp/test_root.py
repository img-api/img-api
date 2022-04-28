from test.unit.apiapp import client

def test_landing(client):
    landing = client.get("/landing/html_check")
    html = landing.data.decode()

    # Spot check important text
    assert "Landing check" in html
    assert landing.status_code == 200


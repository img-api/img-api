""" Browsers may only use the API with cookies from our own sites; media files can be embedded anywhere. """
from imgapi_launcher import app


def cors(path, origin, method="GET"):
    with app.test_client() as c:
        if method == "OPTIONS":
            ret = c.options(path, headers={"Origin": origin, "Access-Control-Request-Method": "POST",
                                           "Access-Control-Request-Headers": "Content-Type"})
        else:
            ret = c.get(path, headers={"Origin": origin})
        return ret.headers.get("Access-Control-Allow-Origin"), ret.headers.get("Access-Control-Allow-Credentials")


def test_own_site_gets_credentialed_cors():
    assert cors("/api/hello_world/", "https://img-api.com") == ("https://img-api.com", "true")
    assert cors("/api/user/login", "https://dev.img-api.com", "OPTIONS") == ("https://dev.img-api.com", "true")


def test_other_sites_get_no_cors_on_the_api():
    for origin in ("https://evil.example", "https://img-api.com.evil.example", "null"):
        assert cors("/api/user/get/me", origin) == (None, None)
        assert cors("/api/media/update", origin, "OPTIONS") == (None, None)


def test_media_files_can_be_embedded_anywhere_without_cookies():
    allow, creds = cors("/api/media/get/000000000000000000000000.jpg", "https://linkslog.org")
    # flask-cors echoes the origin instead of "*": same thing, as long as no cookies are allowed
    assert allow in ("*", "https://linkslog.org") and creds is None

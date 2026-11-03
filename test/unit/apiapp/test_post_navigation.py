""" Next/previous on a single post walks the post owner's photostream. """
import io
import subprocess

import pytest

from imgapi_launcher import app
from test.unit.apiapp import client  # noqa: F401  (fixture, logged in as "dummy")
from test.unit.apiapp.test_smoke import make_video

VIEWER = "username=viewer&email=viewer@engineer.blue&password=test1234"


def upload(client, name):
    data = dict(image=(io.BytesIO(make_video()), name))
    ret = client.post("/api/media/upload", content_type="multipart/form-data", data=data)
    assert ret.json["status"] == "success", ret.json
    media_id = ret.json["media_files"][0]["media_id"]
    ret = client.get("/api/media/posts/" + media_id + "/set_privacy/public")
    assert ret.json["status"] == "success", ret.json
    return media_id


@pytest.fixture
def viewer():
    c = app.test_client()
    c.get("/api/user/remove?" + VIEWER)
    assert c.get("/api/user/create?" + VIEWER).json["status"] == "success"
    assert c.get("/api/user/login?" + VIEWER).json["status"] == "success"
    yield c
    c.get("/api/user/remove?" + VIEWER)


def neighbours(c, media_id):
    nxt = c.get("/api/media/posts/" + media_id + "/get?next=posts")
    prv = c.get("/api/media/posts/" + media_id + "/get?prev=posts")
    ids = lambda r: [m["media_id"] for m in r.json.get("media_files", [])] if r.status_code == 200 else r.status_code
    return ids(nxt), ids(prv)


@pytest.mark.skipif(subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0, reason="no ffmpeg")
def test_next_prev_uses_owner_stream(client, viewer):
    first = upload(client, "nav_a.mp4")
    second = upload(client, "nav_b.mp4")
    try:
        owner_view = neighbours(client, first)
        anon_view = neighbours(app.test_client(), first)
        # A different logged-in user must see the same neighbours as the owner and anonymous visitors
        assert neighbours(viewer, first) == owner_view == anon_view
        found = [m for side in owner_view if isinstance(side, list) for m in side]
        assert second in found
    finally:
        for m in (first, second):
            client.get("/api/media/remove/" + m)

""" Next/previous on a single post walks the post owner's photostream. """
import io
import os
import subprocess
import tempfile

import pytest

from imgapi_launcher import app
from test.unit.apiapp import client  # noqa: F401  (fixture, logged in as "dummy")

VIEWER = "username=viewer&email=viewer@engineer.blue&password=test1234"


def distinct_video(seed):
    """ A short test video whose bytes depend on seed (the server de-duplicates by checksum) """
    path = tempfile.mktemp(suffix=".mp4")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c=0x{seed * 40 % 256:02x}4080:size=160x90:rate=10",
                    "-t", "1", "-pix_fmt", "yuv420p", "-c:v", "libx264", path], check=True)
    with open(path, "rb") as f:
        data = f.read()
    os.remove(path)
    return data


_seed = iter(range(1, 1000))


def upload(client, name):
    data = dict(image=(io.BytesIO(distinct_video(next(_seed))), name))
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


@pytest.mark.skipif(subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0, reason="no ffmpeg")
def test_post_reports_favs_for_logged_in_user(client):
    media_id = upload(client, "favs.mp4")
    post = lambda c: c.get("/api/media/posts/" + media_id + "/get").json["media_files"][0]
    try:
        assert post(client)["favs"] is False
        assert client.get("/api/user/media/" + media_id + "/toggle/favs").json["status"] == "success"
        assert post(client)["favs"] is True
        assert "favs" not in post(app.test_client())  # anonymous visitors don't get it
        client.get("/api/user/media/" + media_id + "/toggle/favs")
        assert post(client)["favs"] is False
    finally:
        client.get("/api/media/remove/" + media_id)


@pytest.mark.skipif(subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0, reason="no ffmpeg")
def test_gallery_navigation_hides_private_media_from_visitors(client, viewer):
    from api.galleries.models import DB_MediaList

    a, b, c = (upload(client, n) for n in ("gal_a.mp4", "gal_b.mp4", "gal_c.mp4"))
    try:
        assert client.get("/api/media/posts/" + b + "/set_privacy/private").json["status"] == "success"
        for m in (a, b, c):
            assert client.get("/api/user/media/" + m + "/append/navtest").json["status"] == "success"

        nxt = lambda cl, query: cl.get("/api/media/posts/" + a + "/get?" + query)

        # The owner sees every item in order; visitors skip the private one
        assert nxt(client, "next=navtest").json["media_files"][0]["media_id"] == b
        assert nxt(viewer, "next=navtest").json["media_files"][0]["media_id"] == c
        assert nxt(app.test_client(), "next=navtest").json["media_files"][0]["media_id"] == c

        # A visitor asking for a gallery that doesn't exist gets a 404 and nothing is written
        lists_before = DB_MediaList.objects.count()
        assert nxt(viewer, "next=no_such_gallery").status_code == 404
        assert DB_MediaList.objects.count() == lists_before
    finally:
        for m in (a, b, c):
            client.get("/api/media/remove/" + m)

""" Smoke tests for the endpoints the React frontend calls. """
import io
import os
import subprocess
import tempfile

import pytest

from test.unit.apiapp import client


def make_video():
    """ A 1 second H.264 test video made with ffmpeg """
    path = tempfile.mktemp(suffix=".mp4")
    subprocess.run([
        "ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=10", "-t", "1",
        "-pix_fmt", "yuv420p", "-c:v", "libx264", path
    ], check=True)
    with open(path, "rb") as f:
        data = f.read()
    os.remove(path)
    return data


def test_public_endpoints_anonymous():
    from imgapi_launcher import app
    anon = app.test_client()

    ret = anon.get("/api/hello_world/")
    assert ret.status_code == 200
    assert ret.json["msg"] == "hello world"

    ret = anon.get("/api/user/get/me")
    assert ret.status_code == 401

    ret = anon.get("/api/media/category/NEW")
    assert ret.status_code == 200
    assert ret.json["status"] == "success"

    # The test database has no public galleries
    ret = anon.get("/api/galleries/public/get")
    assert ret.status_code == 404

    ret = anon.get("/api/does/not/exist")
    assert ret.status_code == 404


@pytest.mark.skipif(subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0, reason="no ffmpeg")
def test_video_upload_and_playback(client):
    data = dict(image=(io.BytesIO(make_video()), "smoke_test.mp4"), )
    ret = client.post("/api/media/upload", content_type="multipart/form-data", data=data)
    assert ret.json["status"] == "success", ret.json
    media = ret.json["media_files"][0]
    media_id = media["media_id"]
    assert media["file_type"] == "video"

    # The player gets a redirect to the static file, which Apache serves
    ret = client.get("/api/media/get/" + media_id)
    assert ret.status_code == 302
    assert "/static/MEDIA_FILES/" in ret.headers["Location"]

    # The file is really on disk
    from imgapi_launcher import app
    rel = ret.headers["Location"].split("/static/MEDIA_FILES/")[1]
    assert os.path.getsize(app.config["MEDIA_PATH"] + rel) > 0

    # Poster frame used by the gallery
    ret = client.get("/api/media/get/" + media_id + ".v512.JPG?no_redirect=1")
    assert ret.status_code in (200, 302)

    # Single item view and the user's stream
    ret = client.get("/api/media/posts/" + media_id + "/get")
    assert ret.json["status"] == "success"

    ret = client.get("/api/media/stream/dummy")
    assert ret.json["status"] == "success"
    assert media_id in [m["media_id"] for m in ret.json["media_files"]]

    ret = client.get("/api/user/get/dummy")
    assert ret.json["status"] == "success"

    ret = client.get("/api/media/remove/" + media_id)
    assert ret.json["status"] == "success"

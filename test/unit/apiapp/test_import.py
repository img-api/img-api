""" Import a video from a post link. yt-dlp is replaced by a local file: no network. """
import pytest

from api.media import importer
from test.unit.apiapp import client  # noqa: F401  (fixture, logged in as "dummy")
from test.unit.apiapp.test_post_navigation import distinct_video


@pytest.mark.parametrize("url", [
    "https://x.com/someone/status/1",
    "https://twitter.com/someone/status/1",
    "https://www.reddit.com/r/videos/comments/abc/title/",
    "https://v.redd.it/abc",
    "https://www.instagram.com/reel/abc/",
    "https://youtu.be/abc",
])
def test_accepts_supported_sites(url):
    assert importer.check_import_url(url) == url


def test_embed_mirrors_download_from_x():
    assert importer.check_import_url("https://fxtwitter.com/a/status/1") == "https://x.com/a/status/1"


@pytest.mark.parametrize("url", [
    "", None, "ftp://x.com/a", "file:///etc/passwd", "https://example.com/v.mp4",
    "http://127.0.0.1:5112/api/hello_world/", "https://x.com.evil.example/a", "https://evilx.com/a",
])
def test_refuses_other_links(url):
    with pytest.raises(importer.ImportError_):
        importer.check_import_url(url)


@pytest.fixture
def fake_download(monkeypatch):
    calls = []

    def download(url, folder):
        calls.append(url)
        path = folder + "/media.mp4"
        with open(path, "wb") as f:
            f.write(distinct_video(200))
        return path, {"title": "  A   cat\nvideo ", "webpage_url": url}

    monkeypatch.setattr(importer, "download_video", download)
    return calls


def test_import_creates_a_post_with_title_and_source(client, fake_download):
    url = "https://x.com/someone/status/42"
    ret = client.post("/api/media/import", json={"url": url})
    assert ret.json["status"] == "success", ret.json
    media = ret.json["media_files"][0]
    assert media["file_type"] == "video"
    assert media["my_title"] == "A cat video"
    assert media["my_source_url"] == url
    assert fake_download == [url]

    # Same video again: the existing post comes back, nothing new is stored
    again = client.post("/api/media/import", json={"url": url}).json["media_files"][0]
    assert again["media_id"] == media["media_id"]
    assert again["is_duplicated"]


def test_import_refuses_unsupported_links_without_downloading(client, fake_download):
    ret = client.post("/api/media/import", json={"url": "https://example.com/v.mp4"})
    assert ret.status_code == 400
    assert "supported" in ret.json["error_msg"]
    assert fake_download == []


def test_import_needs_a_login():
    from imgapi_launcher import app
    with app.test_client() as anon:
        ret = anon.post("/api/media/import", json={"url": "https://x.com/a/status/1"})
        assert ret.status_code in (401, 403)

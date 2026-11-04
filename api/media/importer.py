""" Import a video from a post link (X, Reddit, Instagram, YouTube) with yt-dlp.

Only links to those sites are accepted, and yt-dlp may only use their
extractors (never its generic one), so the server can't be used to fetch
arbitrary URLs. The file is downloaded to a temp folder and then goes through
the normal upload code.
"""
import glob
import os
import tempfile
from urllib.parse import urlparse

from flask import current_app

ALLOWED_HOSTS = {
    'x.com', 'twitter.com', 'mobile.twitter.com', 'fxtwitter.com', 'vxtwitter.com',
    'reddit.com', 'old.reddit.com', 'new.reddit.com', 'redd.it', 'v.redd.it',
    'instagram.com',
    'youtube.com', 'm.youtube.com', 'youtu.be',
}
ALLOWED_EXTRACTORS = ['twitter', 'Reddit', 'Instagram', 'youtube', 'youtube:shorts']

MAX_FILESIZE = 300 * 1024 * 1024
MAX_DURATION = 20 * 60


class ImportError_(Exception):
    """ Message is safe to show to the user """


def check_import_url(url):
    if not url or not isinstance(url, str) or len(url) > 2048:
        raise ImportError_("Missing link")
    parsed = urlparse(url.strip())
    if parsed.scheme not in ('http', 'https'):
        raise ImportError_("The link must start with https://")
    host = (parsed.hostname or '').lower()
    if host.startswith('www.'):
        host = host[4:]
    if host not in ALLOWED_HOSTS:
        raise ImportError_("Only X, Reddit, Instagram and YouTube links are supported")
    # fxtwitter/vxtwitter are embed mirrors: download from X itself
    if host in ('fxtwitter.com', 'vxtwitter.com'):
        url = parsed._replace(netloc='x.com').geturl()
    return url.strip()


def _too_long(info, *, incomplete):
    duration = info.get('duration')
    if duration and duration > MAX_DURATION:
        return f"Video is longer than {MAX_DURATION // 60} minutes"
    return None


def download_video(url, folder):
    """ Downloads the post's video into folder. Returns (path, info). """
    import yt_dlp

    opts = {
        'outtmpl': os.path.join(folder, 'media.%(ext)s'),
        # H.264 MP4 plays everywhere; fall back to any MP4, then merge into MP4
        'format': 'bv*[ext=mp4][vcodec^=avc]+ba[ext=m4a]/b[ext=mp4][vcodec^=avc]/bv*[ext=mp4]+ba/b[ext=mp4]/bv*+ba/b',
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'playlist_items': '1',
        'max_filesize': MAX_FILESIZE,
        'match_filter': _too_long,
        'allowed_extractors': ALLOWED_EXTRACTORS,
        'socket_timeout': 30,
        'retries': 2,
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
    }
    cookies = current_app.config.get('YTDLP_COOKIES')
    if cookies and os.path.exists(cookies):
        opts['cookiefile'] = cookies

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        if 'login' in msg.lower() or 'cookies' in msg.lower():
            raise ImportError_("This site needs a login to download that post")
        if 'no video' in msg.lower() or 'unsupported url' in msg.lower():
            raise ImportError_("No video found in that post")
        raise ImportError_("Could not download that post")

    if info and info.get('_type') == 'playlist' and info.get('entries'):
        info = info['entries'][0]

    files = [f for f in glob.glob(os.path.join(folder, 'media.*')) if not f.endswith('.part')]
    if not files:
        reason = info and info.get('__skip_reason')
        raise ImportError_(reason or "No video found in that post (or it is too big)")
    path = files[0]
    if not path.lower().endswith('.mp4'):
        raise ImportError_("That post's video is not in a supported format")
    return path, info or {}


def title_from_info(info):
    title = info.get('title') or info.get('description') or ''
    title = ' '.join(title.split())
    return title[:200]


def import_from_url(url, upload):
    """ upload(file_storage, extra_fields) -> Flask response. Runs the download and hands the file over. """
    from werkzeug.datastructures import FileStorage

    url = check_import_url(url)
    with tempfile.TemporaryDirectory(prefix='imgapi-import-') as folder:
        path, info = download_video(url, folder)
        extra = {'my_source_url': info.get('webpage_url') or url}
        title = title_from_info(info)
        if title:
            extra['my_title'] = title
        with open(path, 'rb') as fp:
            fs = FileStorage(stream=fp, filename='media.mp4', content_type='video/mp4', name='video')
            return upload(fs, extra)

""" Describe public videos with lepochi's GPU worker, for search and the cats gallery.

The GPU box sits behind NAT and pulls work from lepochi.com, so img-api queues
jobs there (lepochi_learn: apps/api/src/worker/external.ts) and collects the
answers later. Each job is a `review` of the video's 512px poster frame; the
answer is a paragraph ending in "Visible objects: cat, sofa, ...".

Per run (systemd timer, every 15 minutes):
  1. collect finished jobs: store the paragraph in `auto_description`, the
     object list in `auto_tags`, and add cat videos to the cats gallery
     (by reference, no copy);
  2. top the queue up to DESCRIBE_MAX_OUTSTANDING.

State per video lives in `auto_describe_state`: queued, done, failed or
no_preview. Run by hand with:  python -m api.media.describe [--dry-run]
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta

import requests

PUBLIC_BASE = 'https://img-api.com'
MAX_OUTSTANDING = 300
BATCH = 200
# Lepochi deletes finished jobs after a week; anything queued longer was lost.
LOST_AFTER = timedelta(days=8)

CAT_WORDS = {'cat', 'cats', 'kitten', 'kittens', 'kitty', 'kitties'}
MAX_TAGS = 20


def parse_objects(description):
    """ "Visible objects: a cat, two cushions." -> ['cat', 'cushions'] """
    match = re.search(r'visible objects\s*:\s*(.+)', description or '', re.IGNORECASE)
    if not match:
        return []
    tags = []
    for raw in re.split(r'[,;]', match.group(1).split('\n')[0]):
        tag = raw.strip().strip('.').lower()
        tag = re.sub(r'^(a|an|the|some|two|three|several|many)\s+', '', tag)
        if tag and len(tag) <= 40 and tag not in tags:
            tags.append(tag)
    return tags[:MAX_TAGS]


def is_cat(description, tags):
    words = set()
    for tag in tags:
        words.update(tag.split())
    if words & CAT_WORDS:
        return True
    # The object line is sometimes missing; the paragraph still names the cat.
    return bool(re.search(r'\b(cats?|kittens?|kitty)\b', description or '', re.IGNORECASE))


class Lepochi:
    def __init__(self, url, token):
        self.url = url.rstrip('/')
        self.headers = {'Authorization': 'Bearer ' + token}

    def enqueue(self, jobs):
        r = requests.post(self.url, json={'app': 'imgapi', 'jobs': jobs}, headers=self.headers, timeout=30)
        r.raise_for_status()
        return r.json()

    def finished(self, since, limit=200):
        r = requests.get(self.url, params={'app': 'imgapi', 'since': since, 'limit': limit},
                         headers=self.headers, timeout=30)
        r.raise_for_status()
        return r.json()


def cats_gallery():
    from api.galleries.models import DB_MediaList
    from flask import current_app

    gallery_id = current_app.config.get('CATS_GALLERY_ID')
    if gallery_id:
        return DB_MediaList.objects(id=gallery_id).first()
    return DB_MediaList.objects(username='cats', name='cats').first()


def add_to_gallery(gallery, media_id):
    """ Adds a reference, once. A queryset update, so it doesn't need a logged-in owner. """
    from api.galleries.models import DB_ItemMedia, DB_MediaList

    item = DB_ItemMedia(media_id=media_id, update_date=datetime.now())
    return DB_MediaList.objects(id=gallery.id, media_list__media_id__ne=media_id).update_one(push__media_list=item)


def apply_result(job, gallery, log):
    from api.media.models import File_Tracking

    media = File_Tracking.objects(id=job['id']).first()
    if not media:
        return
    now = datetime.now()
    if job['status'] != 'done' or not job.get('description'):
        File_Tracking.objects(id=media.id).update_one(
            set__auto_describe_state='failed', set__auto_describe_date=now,
            set__auto_describe_error=(job.get('error') or 'no description')[:300])
        log(f"failed {media.id}: {job.get('error')}")
        return

    description = job['description'].strip()[:4000]
    tags = parse_objects(description)
    File_Tracking.objects(id=media.id).update_one(
        set__auto_description=description, set__auto_tags=tags,
        set__auto_describe_state='done', set__auto_describe_date=now)

    if gallery and media.is_public and is_cat(description, tags):
        if add_to_gallery(gallery, str(media.id)):
            log(f"cat {media.id} -> gallery {gallery.id}")


def collect(lepochi, state, gallery, log):
    since = state.get('since') or '1970-01-01T00:00:00Z'
    total = 0
    while True:
        page = lepochi.finished(since)
        jobs = page.get('jobs') or []
        for job in jobs:
            apply_result(job, gallery, log)
        total += len(jobs)
        if jobs:
            since = jobs[-1]['updatedAt']
            state['since'] = since
        if len(jobs) < 200:
            return total, page.get('queue') or {}


def poster_exists(media):
    from api.media.models import File_Tracking

    return os.path.exists(File_Tracking.get_media_path() + media.file_path + '.PREVIEW.PNG')


def top_up(lepochi, queue, log, dry_run=False):
    from api.media.models import File_Tracking
    from flask import current_app

    # Lost jobs go back in the pool
    File_Tracking.objects(auto_describe_state='queued', auto_describe_date__lt=datetime.now() - LOST_AFTER) \
        .update(unset__auto_describe_state=True)

    limit = int(current_app.config.get('DESCRIBE_MAX_OUTSTANDING', MAX_OUTSTANDING))
    room = limit - (queue.get('queued', 0) + queue.get('claimed', 0))
    if room <= 0:
        return 0

    candidates = File_Tracking.objects(file_type='video', is_public=True, auto_describe_state__exists=False) \
        .order_by('-creation_date').only('id', 'file_path').limit(room)

    jobs = []
    for media in candidates:
        if not media.file_path or not poster_exists(media):
            if not dry_run:
                File_Tracking.objects(id=media.id).update_one(set__auto_describe_state='no_preview')
            continue
        jobs.append({'id': str(media.id), 'imageUrl': f"{PUBLIC_BASE}/api/media/get/{media.id}.v512.JPG"})

    if dry_run:
        log(f"would queue {len(jobs)}")
        return len(jobs)

    for i in range(0, len(jobs), BATCH):
        chunk = jobs[i:i + BATCH]
        lepochi.enqueue(chunk)
        File_Tracking.objects(id__in=[j['id'] for j in chunk]).update(
            set__auto_describe_state='queued', set__auto_describe_date=datetime.now())
    return len(jobs)


def load_state(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(path, state):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(state, f)
    os.replace(tmp, path)


def run(dry_run=False):
    from flask import current_app

    def log(msg):
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), msg, flush=True)

    url = current_app.config.get('LEPOCHI_JOBS_URL')
    token = current_app.config.get('LEPOCHI_JOBS_TOKEN')
    if not url or not token:
        log("LEPOCHI_JOBS_URL / LEPOCHI_JOBS_TOKEN not configured, nothing to do")
        return 1

    state_path = current_app.config.get('DESCRIBE_STATE_FILE') or os.path.expanduser('~/.imgapi-describe.json')
    state = load_state(state_path)
    lepochi = Lepochi(url, token)
    gallery = cats_gallery()
    if not gallery:
        log("no cats gallery found, cats won't be collected")

    collected, queue = (0, {}) if dry_run else collect(lepochi, state, gallery, log)
    if not dry_run:
        save_state(state_path, state)
    queued = top_up(lepochi, queue, log, dry_run)
    log(f"collected {collected}, queued {queued}, lepochi queue {queue}")
    return 0


if __name__ == '__main__':
    from imgapi_launcher import app

    with app.app_context():
        sys.exit(run(dry_run='--dry-run' in sys.argv))

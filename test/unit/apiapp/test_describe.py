""" Video descriptions from lepochi's worker: tags, cats gallery, queueing """
import os

import pytest
from imgapi_launcher import app

from api.media import describe

DESC = ("A grey cat sleeps on a red sofa next to a window.\n\n"
        "Visible objects: a cat, sofa, two cushions, the window.")


def test_parse_objects():
    assert describe.parse_objects(DESC) == ['cat', 'sofa', 'cushions', 'window']
    assert describe.parse_objects("No list here") == []
    assert describe.parse_objects("visible objects: Dog; dog; Ball") == ['dog', 'ball']


def test_is_cat():
    assert describe.is_cat(DESC, describe.parse_objects(DESC))
    assert describe.is_cat("Two kittens play with yarn.", [])
    assert describe.is_cat("x", ['black cat'])
    assert not describe.is_cat("A caterpillar on a leaf. A man in a catsuit.", ['caterpillar', 'leaf'])


class FakeLepochi:
    def __init__(self, finished=None):
        self.queued = []
        self.pages = [finished or []]

    def enqueue(self, jobs):
        self.queued.extend(jobs)
        return {'queued': len(jobs)}

    def finished(self, since, limit=200):
        jobs = self.pages.pop(0) if self.pages else []
        return {'jobs': jobs, 'queue': {'queued': len(self.queued)}}


@pytest.fixture
def world(tmp_path):
    from api.galleries.models import DB_MediaList
    from api.media.models import File_Tracking

    old_media_path = app.config.get('MEDIA_PATH')
    with app.app_context():
        app.config['MEDIA_PATH'] = str(tmp_path) + '/'
        os.makedirs(tmp_path / 'u', exist_ok=True)
        videos = []
        for name, public, poster in [('a', True, True), ('b', True, False), ('c', False, True)]:
            m = File_Tracking(username='describe_test', file_type='video', is_public=public,
                              file_path=f'u/{name}.MP4', file_name=f'{name}.mp4')
            m.save(is_admin=True)
            if poster:
                (tmp_path / 'u' / f'{name}.MP4.PREVIEW.PNG').write_bytes(b'png')
            videos.append(m)
        gallery = DB_MediaList(username='describe_test', name='cats_test', is_public=True)
        gallery.save(is_admin=True)
        app.config['CATS_GALLERY_ID'] = str(gallery.id)
        yield videos, gallery
        File_Tracking.objects(username='describe_test').delete()
        DB_MediaList.objects(username='describe_test').delete()
        app.config.pop('CATS_GALLERY_ID', None)
        app.config['MEDIA_PATH'] = old_media_path


def test_top_up_queues_public_videos_with_a_poster(world):
    from api.media.models import File_Tracking
    videos, _ = world
    lepochi = FakeLepochi()
    with app.app_context():
        describe.top_up(lepochi, {}, print)
        ids = [j['id'] for j in lepochi.queued]
        assert str(videos[0].id) in ids
        assert str(videos[1].id) not in ids   # no poster
        assert str(videos[2].id) not in ids   # private
        job = next(j for j in lepochi.queued if j['id'] == str(videos[0].id))
        assert job['imageUrl'] == f"https://img-api.com/api/media/get/{videos[0].id}.v512.JPG"
        assert File_Tracking.objects(id=videos[0].id).first().auto_describe_state == 'queued'
        assert File_Tracking.objects(id=videos[1].id).first().auto_describe_state == 'no_preview'

        # Nothing is queued twice
        again = FakeLepochi()
        describe.top_up(again, {}, print)
        assert str(videos[0].id) not in [j['id'] for j in again.queued]


def test_top_up_respects_the_outstanding_limit(world):
    with app.app_context():
        lepochi = FakeLepochi()
        assert describe.top_up(lepochi, {'queued': 250, 'claimed': 50}, print) == 0
        assert lepochi.queued == []


def test_results_become_tags_and_cats_join_the_gallery_once(world):
    from api.galleries.models import DB_MediaList
    from api.media.models import File_Tracking
    videos, gallery = world
    vid = str(videos[0].id)
    done = {'id': vid, 'status': 'done', 'description': DESC, 'updatedAt': '2026-11-04T10:00:00Z'}
    with app.app_context():
        state = {}
        describe.collect(FakeLepochi([done]), state, describe.cats_gallery(), print)
        describe.collect(FakeLepochi([done]), state, describe.cats_gallery(), print)
        media = File_Tracking.objects(id=vid).first()
        assert media.auto_describe_state == 'done'
        assert media.auto_tags == ['cat', 'sofa', 'cushions', 'window']
        assert media.auto_description.startswith('A grey cat')
        refs = [i.media_id for i in DB_MediaList.objects(id=gallery.id).first().media_list]
        assert refs == [vid]
        assert state['since'] == '2026-11-04T10:00:00Z'
        # The file itself is untouched: still the original owner's
        assert media.username == 'describe_test'


def test_failed_jobs_are_marked(world):
    from api.media.models import File_Tracking
    videos, _ = world
    vid = str(videos[0].id)
    with app.app_context():
        describe.collect(FakeLepochi([{'id': vid, 'status': 'dead', 'error': 'fetch image 404',
                                       'updatedAt': '2026-11-04T10:00:00Z'}]), {}, None, print)
        media = File_Tracking.objects(id=vid).first()
        assert media.auto_describe_state == 'failed'
        assert 'auto_tags' not in media or media.auto_tags == []

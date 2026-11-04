""" What strangers can read: other people's profiles and the public comment search """
from imgapi_launcher import app
from test.unit.apiapp import client

PRIVATE_KEYS = ['referral', 'share_referral_code', 'subscription', 'subscription_status', 'is_valid', 'lang']


def set_public(username, is_public):
    from api.user.models import User
    with app.app_context():
        User.objects(username=username).update(is_public=is_public)


def test_strangers_only_see_public_basics(client):
    stranger = app.test_client()
    ret = stranger.get("/api/user/get/dummy")
    assert ret.status_code == 200
    user = ret.json['user']
    assert user['username'] == 'dummy'
    for key in PRIVATE_KEYS:
        assert key not in user, key


def test_owner_still_sees_everything(client):
    ret = client.get("/api/user/get/me?key=" + client.environ_base['user_token'])
    assert ret.status_code == 200
    assert 'share_referral_code' in ret.json['user']
    assert 'settings' in ret.json['user']


def test_private_account_is_not_found_for_strangers(client):
    set_public('dummy', False)
    try:
        assert app.test_client().get("/api/user/get/dummy").status_code == 401
        ret = client.get("/api/user/get/dummy?key=" + client.environ_base['user_token'])
        assert ret.status_code == 200
    finally:
        set_public('dummy', True)


def test_sign_up_returns_own_details(client):
    stranger = app.test_client()
    creds = "username=privacy_test&email=privacy_test@engineer.blue&password=test1234test"
    stranger.get("/api/user/remove?" + creds)
    try:
        ret = app.test_client().get("/api/user/create?" + creds)
        assert ret.json['status'] == 'success'
        assert 'share_referral_code' in ret.json['user']
    finally:
        stranger.get("/api/user/remove?" + creds)


def test_comment_query_allows_normal_filters(client):
    ret = app.test_client().get("/api/comments/query?parent_obj_id=abc&order_by=-creation_date")
    assert ret.status_code == 200
    assert ret.json['comments'] == []


def test_comment_query_refuses_other_fields_and_regex(client):
    stranger = app.test_client()
    for query in ["old_content__icontains=a", "content__regex=.*", "parent_obj_id__regex=a",
                  "and--old_title=x", "parent_obj_id=a&order_by=old_content"]:
        ret = stranger.get("/api/comments/query?" + query)
        assert ret.status_code == 400, query

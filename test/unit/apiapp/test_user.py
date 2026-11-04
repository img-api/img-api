from test.unit.apiapp import client


def test_user(client):

    TEST_CREDENTIALS = "username=user_test&email=user_test@engineer.blue&password=test1234test"

    # Delete the user in case we have it already there.
    ret = client.get("/api/user/remove?" + TEST_CREDENTIALS)

    # Create an user
    ret = client.get("/api/user/create?" + TEST_CREDENTIALS)
    assert ret.json['status'] == 'success'

    # User has been already created, should return that is a duplicate
    ret = client.get("/api/user/create?" + TEST_CREDENTIALS)
    assert ret.json['status'] == 'success'
    assert ret.json['duplicate'] == True

    # Check login
    ret = client.get("/api/user/login?" + TEST_CREDENTIALS)
    assert ret.json['status'] == 'success'

    user_token = ret.json['token']

    print("TOKEN [" + user_token + "]")

    # Replace credentials with token
    TEST_CREDENTIALS = "key=" + user_token

    # Get if the user is logged in
    ret = client.get("/api/user/token?" + TEST_CREDENTIALS)
    assert ret.json['status'] == 'success'

    # Check if we have an invalid token. From now on every operation should go with this token

    # We test if the system returns OK when offered the wrong token
    ret = client.get("/api/user/token?key=" + user_token[10])
    assert ret.json['status'] != 'success'

    ###################### Media lists ################################

    # Get the favourite list from this user
    ret = client.get("/api/user/me/list/favs/get?" + TEST_CREDENTIALS)

    print (ret.json)

    # It should be empty
    assert ret.json['status'] == 'success'
    assert ret.json['name'] == 'favs'

    # Get the favourite list from an invalid user
    ret = client.get("/api/user/01/list/favs/get?" + TEST_CREDENTIALS)
    assert ret.json['status'] == 'error'

    ###################### Clean up ################################

    # Delete the user
    ret = client.get("/api/user/remove?" + TEST_CREDENTIALS)
    assert ret.json['status'] == 'success'

    ret = client.get("/api/user/get_random_name?" + TEST_CREDENTIALS)
    assert ret.json['status'] == 'success'

    name = ret.json['username']
    assert len(name.split("_")) == 3




# Missing or unknown fields get a 401 with a message, never a 500
import pytest as _pytest


@_pytest.mark.parametrize("query", [
    "", "password=whatever123", "username=nobody_xyz", "username=nobody_xyz&password=whatever123",
    "email=nobody@engineer.blue&password=whatever123",
])
def test_login_with_missing_fields_says_why(query):
    from imgapi_launcher import app
    with app.test_client() as c:
        ret = c.get("/api/user/login?" + query)
        assert ret.status_code == 401, ret.data[:200]
        assert ret.json["error_msg"]


def test_create_without_fields_says_why():
    from imgapi_launcher import app
    with app.test_client() as c:
        assert c.get("/api/user/create").status_code == 401
        assert c.post("/api/user/create", json={}).status_code == 401


def test_recovery_with_unknown_user_id_says_why():
    from imgapi_launcher import app
    with app.test_client() as c:
        assert c.get("/api/user/password_recovery?user_id=000000000000000000000000").status_code == 401

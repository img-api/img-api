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

    # Get if the user is logged in
    ret = client.get("/api/user/token?key=" + user_token)
    assert ret.json['status'] == 'success'

    # Check if we have an invalid token. From now on every operation should go with this token

    # We test if the system returns OK when offered the wrong token
    ret = client.get("/api/user/token?key=" + user_token[10])
    assert ret.json['status'] != 'success'

    ###################### Media lists ################################

    # Get the favourite list from this user
    ret = client.get("/api/user/me/list/favs/get?" + TEST_CREDENTIALS)

    # It should be empty
    assert ret.json['status'] == 'success'
    assert ret.json['is_empty']

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



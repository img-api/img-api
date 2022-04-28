from test.unit.apiapp import client

def test_user(client):

    # Delete the user in case we have it already there.
    ret = client.get("/api/user/remove?email=test@engineer.blue&password=test1234")
    assert ret.json['status'] == 'error'

    # Create an user
    ret = client.get("/api/user/create?email=test@engineer.blue&password=test1234")
    assert ret.json['status'] == 'success'

    # User has been already created, should return an error
    ret = client.get("/api/user/create?email=test@engineer.blue&password=test1234")
    assert ret.json['status'] == 'error'

    # Check login
    ret = client.get("/api/user/login?email=test@engineer.blue&password=test1234")
    assert ret.json['status'] == 'success'

    user_token = ret.json['token']

    # Get if the user is logged in
    ret = client.get("/api/user/token?key=" + user_token)
    assert ret.json['status'] == 'success'

    # Check if we have an invalid token. From now on every operation should go with this token
    ret = client.get("/api/user/token?key=" + user_token[10])
    assert ret.json['status'] != 'success'

    # Delete the user
    ret = client.get("/api/user/remove?email=test@engineer.blue&password=test1234")
    assert ret.json['status'] == 'success'


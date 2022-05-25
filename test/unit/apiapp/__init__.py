import pytest
from imgapi_launcher import app
"""Initialize the testing environment

Creates an app for testing that has the configuration flag ``TESTING`` set to
``True``.

"""

def create_test_user(client):
    """ We need an API key to perform operations
        This will create an API key and keep it until the tests are done.
    """

    DUMMY_CREDENTIALS = client.environ_base['DUMMY_CREDENTIALS']

    # Remove the user in case it was already on the system due a failure on the previous test run
    client.get("/api/user/remove?" + DUMMY_CREDENTIALS)

    # Create an user
    ret = client.get("/api/user/create?" + DUMMY_CREDENTIALS)
    assert ret.json['status'] == 'success'

    # Check login
    ret = client.get("/api/user/login?" + DUMMY_CREDENTIALS)
    assert ret.json['status'] == 'success'
    client.environ_base['user_token'] = ret.json['token']

def remove_test_user(client):
    # Remove login
    DUMMY_CREDENTIALS = client.environ_base['DUMMY_CREDENTIALS']

    ret = client.get("/api/user/remove?" + DUMMY_CREDENTIALS)
    #assert ret.json['status'] == 'success'


@pytest.fixture
def client():
    """Configures the app for testing

    Sets app config variable ``TESTING`` to ``True``

    :return: App for testing
    """

    #app.config['TESTING'] = True
    client = app.test_client()
    client.environ_base['DUMMY_CREDENTIALS'] = "username=dummy&email=dummy@engineer.blue&password=test1234"

    create_test_user(client)
    yield client

    remove_test_user(client)

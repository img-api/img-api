""" Every test run uses a throwaway database and media folder, never a real one. """
import os
import shutil
import tempfile

import pytest

TEST_DB = "imgapi_pytest"
MEDIA_DIR = tempfile.mkdtemp(prefix="imgapi_pytest_media_")

os.environ["IMGAPI_MONGODB_HOST"] = "mongodb://localhost/" + TEST_DB
os.environ["IMGAPI_MEDIA_PATH"] = MEDIA_DIR + "/"
os.environ.setdefault("IMGAPI_SECRET_KEY", "pytest-secret")


@pytest.fixture(scope="session", autouse=True)
def throwaway_database():
    import mongoengine
    from imgapi_launcher import app

    assert app.config["MONGODB_SETTINGS"]["host"].endswith("/" + TEST_DB)
    mongoengine.get_connection().drop_database(TEST_DB)
    yield
    mongoengine.get_connection().drop_database(TEST_DB)
    shutil.rmtree(MEDIA_DIR, ignore_errors=True)

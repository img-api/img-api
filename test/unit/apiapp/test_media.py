import io
import os
import math
import requests

from test.unit.apiapp import client

from wand.image import Image
from wand.drawing import Drawing
from wand.color import Color


def test_media(client):
    #
    # Calls the API to upload images and check that they can be converted between formats
    #
    # Uploads a dummy genereated file to the system so we can check against it.
    #
    # We should be able to test pixel perfect matching
    #

    url_upload = "/api/media/upload"

    # Upload a 'broken' image
    data = dict(image=(io.BytesIO(b'my file contents'), "work_order.123"), )
    response = client.post(url_upload, content_type='multipart/form-data', data=data)

    # This upload should fail since we have the wrong file and extension
    assert response.json['status'] != 'success'

    # Upload a generated image so we can perform operationes on it

    test_media = None
    with Drawing() as draw:
        with Image(width=256, height=256, background=Color('blue')) as img:
            draw.font = 'Times New Roman'
            draw.font_size = 20
            draw.text(int(img.width / 3), int(img.height / 2), 'Testing')
            draw(img)

            bit_image = io.BytesIO()
            img.format = "PNG"
            img.save(file=bit_image)
            bit_image.seek(0)

            data = dict(image=(bit_image, "image_uploaded_by_test.png"), )
            response = client.post(url_upload, content_type='multipart/form-data', data=data)
            assert response.json['status'] == 'success'

            test_media = response.json['media'][0]

    assert test_media != None

    ###################### Begin Media lists ################################

    # We append a media to a list of favourites
    ret = client.get("/api/user/media/" + test_media['media_id'] + "/append/favs")
    assert ret.json['status'] == 'success'

    # Get all the lists for this user
    ret = client.get("/api/user/list/get")
    assert ret.json['status'] == 'success'
    assert "favs" in ret.json['galleries']

    # Check the list
    ret = client.get("/api/user/me/list/favs/get")
    assert ret.json['status'] == 'success'
    assert "media_files" in ret.json
    assert len(ret.json["media_files"]) == 1

    # Check the list
    ret = client.get("/api/user/" + "dummy" + "/list/favs/get")
    assert ret.json['status'] == 'success'
    assert "media_files" in ret.json
    assert len(ret.json["media_files"]) == 1

    ###################### End Media lists ################################

    # Check that the info is correct
    assert test_media['info']['width'] == 256
    assert test_media['info']['height'] == 256

    # Do we get a PNG ?
    response = client.get("/api/media/get/" + test_media['media_id'] + "?no_redirect=1")
    assert response.content_type == "image/png"

    # Do we get a GIF ?
    response = client.get("/api/media/get/" + test_media['media_id'] + ".GIF?no_redirect=1")
    assert response.content_type == "image/GIF"

    # Do we get a JPG ?
    response = client.get("/api/media/get/" + test_media['media_id'] + ".JPG?no_redirect=1")
    assert response.content_type == "image/JPG"

    # Upload image from disk with a different orientation than normal so we need to get a rotated width and height
    abs_path = os.path.dirname(__file__)
    with open(abs_path + "/testing_images/wrong_orientation.jpg", 'rb') as fp:
        data = dict(image=(fp, "image_uploaded_wrong_orientation.jpg"), )
        response = client.post(url_upload, content_type='multipart/form-data', data=data)
        assert response.json['status'] == 'success'

        test_media = response.json['media'][0]

        assert test_media['file_size'] == 190684
        assert test_media['info']['width'] == 480
        assert test_media['info']['height'] == 800
        assert test_media['checksum_md5'] == "7d2ff2b65e707b5fbedd4c5f72fa9687"

    # Delete the file on disk
    response = client.get("/api/media/remove/" + test_media['media_id'])
    assert response.json['status'] == "success"
    assert response.json['deleted'] == True

import io
import os
import json
import math
import requests

from test.unit.apiapp import client

from wand.image import Image
from wand.drawing import Drawing
from wand.color import Color


def test_gallery(client):
    #
    # Creates a Gallery
    #
    # Uploads a dummy genereated file to the gallery so we can check against it.
    #

    url_gallery = "/api/user/list/create"

    gallery_data = {
        'title': "Unit testing gallery",
        'is_unlisted': True
    }

    response = client.post(url_gallery, content_type='application/json', data=json.dumps(gallery_data))

    assert response.json['status'] == 'success'
    assert len(response.json['galleries']) == 1

    gallery = response.json['galleries'][0]
    gallery_id = gallery['id']

    url_upload = "/api/media/upload?gallery_id=" + gallery_id

    # Upload a generated image so we can perform operationes on it

    test_media = None
    with Drawing() as draw:
        with Image(width=256, height=256, background=Color('blue')) as img:
            draw.font = 'Times New Roman'
            draw.font_size = 20
            draw.text(int(img.width / 3), int(img.height / 2), 'Testing Gallery')
            draw(img)

            bit_image = io.BytesIO()
            img.format = "PNG"
            img.save(file=bit_image)
            bit_image.seek(0)

            data = dict(image=(bit_image, "image_uploaded_by_test.png"), )
            response = client.post(url_upload, content_type='multipart/form-data', data=data)
            assert response.json['status'] == 'success'

            test_media = response.json['media_files'][0]
            assert test_media['is_public'] == True
            assert test_media['is_unlisted'] == True

    assert test_media != None

    url_toggle_public = "/api/media/" + test_media['media_id'] + "/set/is_public?value=false"

    response = client.post(url_toggle_public, content_type='application/json', data=json.dumps({}))
    assert response.json['status'] == 'success'


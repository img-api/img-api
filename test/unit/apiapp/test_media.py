import io
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

            url_upload = "/api/media/upload"

            data = dict(image=(bit_image, "image_uploaded_by_test.png"), )
            response = client.post(url_upload, content_type='multipart/form-data', data=data)
            assert response.json['status'] == 'success'

            # Upload a 'broken' image
            data = dict(image=(io.BytesIO(b'my file contents'), "work_order.123"), )
            response = client.post(url_upload, content_type='multipart/form-data', data=data)

            # This upload should fail since we have the wrong file and extension
            assert response.json['status'] != 'success'

            # Real upload online
            # files = {'image_uploaded_by_test.png': bit_image}
            # requests.post(url_upload, files=files)

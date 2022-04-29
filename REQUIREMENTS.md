# SITE REQUIREMENTS

This system defines an API to manage images and perform operations on them.
We are creating a processing engine that can perform asynchronous operations.

## API

### Functionality

A simple service that can receive an uploaded image and return a unique identifier
for the uploaded image that can be used subsequently to retrieve the image.

* Registration
* Token
* Upload Image
    - Direct upload
    - Download from a specific URL
    - Convert the file on the fly to different formats directly on the API

* Download
* Perform operation
    - Compression
    - Rotation
    - Filters
    - Thumbnail creation
    - Masking
    - Format conversion

* List of images for the user

Extend the service so that different image formats can be returned by using a different
image file type as an extension on the image request URL.

### Tests

* Write a series of tests that test the image upload, download and file format conversion capabilities.

Write a series of tests that test the image upload, download and file format conversion
capabilities.

### RQ

Write a series of services for each type of image transformation. Coordinate the various
services using RQ and REDIS.

## SITE

For integration testing we will produce the following views:

* Login / Password
* Auth Token generation
* Upload an image
* Perform operations on the image
* Download the image


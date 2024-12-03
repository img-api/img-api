
from api import api_key_login_or_anonymous, get_response_formatted
from api.galleries import blueprint
from api.galleries.models import DB_MediaList
from api.print_helper import *
from api.query_helper import mongo_to_dict_result
from flask import abort, request
from mongoengine.queryset.visitor import Q


@blueprint.route('<string:gallery_type>/get', methods=['GET'])
@api_key_login_or_anonymous
#@cache_for(hours=48, only_if=ResponseIsSuccessfulOrRedirect)
def api_get_galleries(gallery_type):
    """Returns a list of galleries to be displayed, with the current query

    ---
    tags:
      - media
    schemes: ['http', 'https']
    deprecated: false
    definitions:
      image_file:
        type: object
    parameters:
        - in: query
          name: thumbnail
          schema:
            type: string
          description: You can specify a Thumbnail size that will correct the aspect ratio Examples .v256.PNG or .h128.GIF

    responses:
      200:
        description: Returns a file or a generic placeholder for the file
      404:
        description: Galleries don't exist on this group

    """

    query = Q(is_public=True) & (Q(is_unlisted=False) | Q(is_unlisted=None))

    the_list = DB_MediaList.objects(query).exclude('media_list')
    if not the_list:
        return abort(404, "No public galleries")

    galleries = mongo_to_dict_result(the_list)

    ret = {'galleries': galleries}

    return get_response_formatted(ret)


@blueprint.route('/category/<string:media_category>', methods=['GET'])
@api_key_login_or_anonymous
def api_fetch_gallery_with_media_category(media_category):
    """Returns a list of media objects to display.

    This API is only for public media
    ---
    tags:
      - media
    schemes: ['http', 'https']
    deprecated: false
    definitions:
      image_file:
        type: object
    parameters:
        - in: query
          name: media_category
          schema:
            type: string
          description: Just specify from the list of media categories
    responses:
      200:
        description: Returns a list of media files
      401:
        description: User doesn't have access to this resource.
      404:
        description: Category doesn't exist anymore on the system

    """
    from api.media.models import File_Tracking
    from flask_login import \
        current_user  # Required by pytest, otherwise client crashes on CI

    DEFAULT_PAGE_CONTINUE = 3

    DEFAULT_ITEMS_LIMIT = 25
    items = int(request.args.get('items', DEFAULT_ITEMS_LIMIT))
    page = int(request.args.get('page', 0))
    offset = page * items

    query = Q(is_public=True) & (Q(is_unlisted=False) | Q(is_unlisted=None))

    # Skip visited media
    try:
        visited_offset = 0
        if page == DEFAULT_PAGE_CONTINUE:
            visited_offset = int(request.cookies.get('visited_offset_' + media_category, 0))

        elif page > DEFAULT_PAGE_CONTINUE:
            visited_offset = int(request.cookies.get('offset_cat_' + media_category, 0))

        visited_offset -= DEFAULT_PAGE_CONTINUE * items
        if visited_offset > 0:
            offset += visited_offset

    except Exception as e:
        print_exception(e, "Crash")

    if media_category != "NEW":
        query = query & Q(tags__contains=media_category)

    print_h1(" LOAD PAGE " + str(page))

    op = File_Tracking.objects(query)

    if request.args.get('order', 'desc') == 'desc':
        op = op.order_by('-creation_date')
    else:
        op = op.order_by('+creation_date')

    files = op.skip(offset).limit(items)

    return_list = []

    count = 0
    for f in files:
        if f.exists():
            return_list.append(f.serialize())
            count += 1

    if current_user.is_authenticated:
        current_user.populate_media(return_list)

    ret = {'status': 'success', 'media_files': return_list, 'items': items, 'offset': offset, 'page': page}

    resp = get_response_formatted(ret)

    try:
        if count < items:
            print_b(" Reached end of media, reset offset ")
            resp.set_cookie('offset_cat_' + media_category, "0")
            resp.set_cookie('visited_offset_' + media_category, "0")

        elif page == DEFAULT_PAGE_CONTINUE:
            visited_offset = request.cookies.get('visited_offset_' + media_category, 0)
            print_b(" Save new skip " + str(visited_offset))
            resp.set_cookie('offset_cat_' + media_category, str(visited_offset))
        elif page > DEFAULT_PAGE_CONTINUE:
            print_b(" Save new offset " + str(offset))
            resp.set_cookie('visited_offset_' + media_category, str(offset))

    except Exception as e:
        print_exception(e, "Crash")

    return resp

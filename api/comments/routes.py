
from api import (api_key_or_login_required, get_response_error_formatted,
                 get_response_formatted)
from api.comments import blueprint
from api.comments.models import DB_Comments
from api.print_helper import *
from api.query_helper import build_query_from_request
from api.tools.markdownify import markdownify
from flask import request
from flask_login import current_user


def get_comments_count(parent_id):
    # Match stage to filter documents by parent_id
    try:
        match = {'parent_obj_id': parent_id}

        # Group stage to count the documents
        group_stage = {"$group": {"_id": "$parent_obj_id", "count": {"$sum": 1}}}

        # Construct the pipeline
        pipeline = [{"$match": match}, group_stage]

        stats = list(DB_Comments.objects.aggregate(*pipeline))
        if len(stats) == 0:
            return 0

        return stats[0]['count']

    except Exception as e:
        print_exception(e, "Parent")

    return 0


@blueprint.route('/create', methods=['GET', 'POST'])
@api_key_or_login_required
def api_create_new_comment():
    """ Create a new comment
    """

    print("======= CREATE A SINGLE COMMENT =============")

    jrequest = request.json

    if 'id' in jrequest:
        return get_response_error_formatted(400, {'error_msg': "Error, please use UPDATE to update an entry"})

    checks = ['content', 'parent_obj', 'parent_obj_id']
    for check in checks:
        if check not in jrequest:
            return get_response_error_formatted(
                400, {'error_msg': "Missing content, not right format. Please check documentation"})

    if not DB_Comments.check_data(jrequest):
        return get_response_error_formatted(400, {'error_msg': "Sorry, system didn't like your comment"})

    if 'title' in jrequest:
        jrequest['title'] = markdownify(jrequest['title']).strip()

    if current_user.current_subscription == "tier1_monthly":
        jrequest['subscription'] = "star-o"

    elif current_user.current_subscription == "tier2_monthly":
        jrequest['subscription'] = "star"

    elif current_user.current_subscription == "tier3_monthly":
        jrequest['subscription'] = "diamond"

    if current_user.is_admin or current_user.username in ["contact@engineer.blue" or "admin"]:
        jrequest['subscription'] = "certificate"

    jrequest['content'] = markdownify(jrequest['content']).strip()
    comment = DB_Comments(**jrequest)
    comment.save()

    ret = {"comments": [comment]}
    return get_response_formatted(ret)


@blueprint.route('/update', methods=['GET', 'POST'])
@api_key_or_login_required
def api_update_comment():
    """ Update a comment
    """

    jrequest = request.json

    if 'id' not in jrequest:
        return get_response_error_formatted(400, {'error_msg': "Error, please use create to update an entry"})

    checks = ['content']
    for check in checks:
        if check not in jrequest:
            return get_response_error_formatted(
                400, {'error_msg': "Missing content, not right format. Please check documentation"})

    comment = DB_Comments.objects(id=jrequest['id']).first()

    if 'title' in jrequest:
        jrequest['title'] = markdownify(jrequest['title']).strip()

    if 'content' in jrequest:
        jrequest['content'] = markdownify(jrequest['content']).strip()

    jrequest['is_edited'] = True
    comment.update_with_checks(jrequest)
    ret = {"comments": [comment]}
    return get_response_formatted(ret)


@blueprint.route('/delete', methods=['GET', 'POST'])
@api_key_or_login_required
def api_delete_comments_get_query():

    jrequest = request.json

    if 'id' not in jrequest:
        return get_response_error_formatted(400, {'error_msg': "Error, wrong query"})

    comment = DB_Comments.objects(id=jrequest['id']).first()

    if comment.title:
        jrequest['old_title'] = comment.title
        jrequest['title'] = "..."

    if comment.content:
        jrequest['old_content'] = comment.content
        jrequest['content'] = "*(deleted)*"

    jrequest['is_deleted'] = True
    comment.update_with_checks(jrequest)

    if current_user.current_subscription:
        comment.force_update(**{'username': "...redacted..."})

    ret = {"comments": [comment]}
    return get_response_formatted(ret)


@blueprint.route('/query', methods=['GET', 'POST'])
def api_comments_get_query():
    """
    Example of queries: https://domain/api/comments/query?title=NULL
    """

    comments = build_query_from_request(DB_Comments, global_api=True)

    clean = request.args.get("cleanup", None)
    if clean and (current_user.is_admin or current_user.username in ["contact@engineer.blue", "admin"]):
        comments.delete()
        ret = {'status': "deleted"}
        return get_response_formatted(ret)

    cleanup = []

    for comment in comments:
        cleanup.append(comment.serialize())

    ret = {'comments': cleanup}
    return get_response_formatted(ret)


@blueprint.route('/info', methods=['GET', 'POST'])
def api_comments_get_info():
    """
    https://domain/api/comments/info
    """

    id = request.args.get("id")

    ret = {'count': get_comments_count(id)}
    return get_response_formatted(ret)

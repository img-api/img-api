import validators

from flask import abort, send_file
from flask_login import current_user

from api.api_redis import api_rq
from api.jobs import blueprint
from api.media.models import File_Tracking
from api.media.routes import get_media_path
from api import get_response_formatted, get_response_error_formatted


def get_postfix(operation, transformation):
    """ Checks if the name is only alphanumeric, and has hiphens or underscores """

    postfix = operation + "_" + transformation
    if not validators.slug(postfix):
        abort(400, "Malformed operation")

    return "." + postfix + ".PNG"


@blueprint.route('/<string:operation>/<string:transformation>/<string:media_id>', methods=['GET', 'POST'])
def api_convert_image_to_format(operation, transformation, media_id):
    """Returns a JOB ID for the task of fetching this resource. It calls RQ to get the task of converting the file done.
    ---
    tags:
      - jobs
    schemes: ['http', 'https']
    deprecated: false
    definitions:
      job_id:
        type: object
    parameters:
        - in: query
          name: operation
          schema:
            type: string
          description: An operation from the set ['convert', 'filter', 'transform']
        - in: query
          name: transformation
          schema:
            type: string
          description: A service call operation/transformation pair.
            Examples convert=['PNG', 'JPG']
            transform=['rotate_right', 'rotate_left']
            filter=['blur', 'median']
            For more transformations please check the full documentation
        - in: query
          name: media_id
          schema:
            type: string
          description: A valid media_id which belongs to this user or is PUBLIC

    responses:
      200:
        description: Returns a job ID. You have to call /api/jobs/job/{ job_id } to get when it is ready.
        schema:
          id: Job ID
          type: object
          properties:
            job_id:
              type: string
      401:
        description: Internal failure reaching our services

      404:
        description: File not found

      500:
        description: Something went really wrong with this job
    """

    if transformation not in ["PNG", "JPG", "rotate_right", "rotate_left", "thumbnail", "blur", "flop", "median"]:
        return get_response_error_formatted(500, {"error_msg": "SERVER CANNOT UNDERSTAND THIS TRANSFORMATION!"})

    my_file = File_Tracking.objects(pk=media_id).first()
    if not my_file:
        return get_response_error_formatted(404, {"error_msg": "FILE NOT FOUND"})

    post_fix = get_postfix(operation, transformation)
    abs_path = get_media_path() + my_file.file_path

    data = {
        'media_id': media_id,
        'media_path': abs_path,
        'operation': operation,
        'target_path': abs_path + post_fix,
        'transformation': transformation,
        'post_fix': post_fix,
        'media_id': media_id
    }

    job = api_rq.call("worker.convert_image", data)
    if not job:
        return get_response_error_formatted(401, {'error_msg': "Failed reaching the services."})

    ret = {'status': 'success', 'job_id': job.id}
    return get_response_formatted(ret)


@blueprint.route('/job/<string:job_id>', methods=['GET'])
def api_get_media_from_job(job_id):
    """Returns the state of a job_id and it's result
    ---
    tags:
      - jobs
    schemes: ['http', 'https']
    deprecated: false
    definitions:
      request_url:
        type: object
    parameters:
        - in: query
          name: job_id
          schema:
            type: string
          description: A valid ID for a job in the system.
    responses:
      200:
        description: If the job has not completed it will return a json object.
        schema:
          id: Job ID
          type: object
          properties:
            job_id:
              type: string
            result:
              type: string
            job_status:
              type: string

      500:
        description: There was some problem performing this task
    """
    job = api_rq.fetch_job(job_id)

    status = job.get_status()
    if status == "failed":
        return get_response_error_formatted(
            500, {'error_msg': "There was some problem performing this task, please contact an administrator."})

    ret = {'status': 'success', 'job_id': job_id, 'job_status': status}
    if status != "finished":
        return get_response_formatted(ret)

    ret['result'] = job.result
    return get_response_formatted(ret)


@blueprint.route('/get/<string:job_id>', methods=['GET'])
def api_get_result_job(job_id):
    """Returns the file result for an operation, if it is completed, otherwise it will return a status update.
        Not to be used by the website without checking the result of the job first.
    ---
    tags:
      - jobs
    schemes: ['http', 'https']
    deprecated: false
    definitions:
      request_url:
        type: object
    parameters:
        - in: query
          name: job_id
          schema:
            type: string
          description: A valid ID for a job in the system.
    responses:
      200:
        description: If the job has not completed it will return a json object, otherwise you will get a file
        schema:
          id: Job ID
          type: object
          properties:
            job_id:
              type: string
            result:
              type: string
            job_status:
              type: string

      404:
        description: File not found internally

      500:
        description: There was some problem performing this task

    """
    job = api_rq.fetch_job(job_id)

    status = job.get_status()
    if status == "failed":
        if is_api_call():
            return get_response_error_formatted(
                500, {'error_msg': "There was some problem performing this task, please contact an administrator."})
        else:
            return redirect("/static/images/placeholder.jpg")

    if status != "finished":
        if is_api_call():
            return get_response_formatted({'status': 'success', 'job_id': job_id, 'job_status': status})
        else:
            return redirect("/static/images/placeholder.jpg")

        return (ret)

    res = job.result

    my_file = File_Tracking.objects(pk=res['media_id']).first()
    if not my_file:
        if is_api_call():
            return get_response_error_formatted(404, {"error_msg": "FILE NOT FOUND"})
        else:
            return redirect("/static/images/placeholder.jpg")

    if not my_file.is_public and my_file.username != current_user.username:
        if is_api_call():
            return get_response_error_formatted(401, {"error_msg": "FILE IS PRIVATE!"})
        else:
            return redirect("/static/images/placeholder_private.jpg")

    post_fix = get_postfix(res['operation'], res['transformation'])
    abs_path = get_media_path() + my_file.file_path + post_fix
    return send_file(abs_path, attachment_filename=my_file.file_name + post_fix)
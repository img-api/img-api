from api.api_redis import api_rq
from api.transform import blueprint
from api.media.models import File_Tracking
from api.media.routes import get_media_path
from api import get_response_formatted, get_response_error_formatted

@blueprint.route('/<string:operation>/<string:transformation>/<string:media_id>', methods=['GET', 'POST'])
def api_convert_image_to_format(operation, transformation, media_id):
    """Returns a JOB ID for the task of fetching this resource. It calls RQ to get the task of converting the file done.
    ---
    tags:
      - media
    schemes: ['http', 'https']
    deprecated: false
    definitions:
      request_url:
        type: object
    parameters:
        - in: query
          name: request_url
          schema:
            type: string
          description: A valid URL that contains a file format on it.
    responses:
      200:
        description: Returns a job ID
        schema:
          id: Job ID
          type: object
          properties:
            job_id:
              type: string
    """

    if transformation not in ["PNG", "JPG", "rotate_right", "rotate_left", "thumbnail", "filter_blur"]:
        return get_response_error_formatted(500, {"error_msg": "SERVER CANNOT UNDERSTAND THIS TRANSFORMATION!"})

    my_file = File_Tracking.objects(pk=media_id).first()
    if not my_file:
        return get_response_error_formatted(404, {"error_msg": "FILE NOT FOUND"})

    abs_path = get_media_path() + my_file.file_path
    target_path = get_media_path() + my_file.file_path + "_" + transformation

    data = {
        'media_id': media_id,
        'media_path': abs_path,
        'operation': operation,
        'target_path': target_path,
        'transformation': transformation,
    }

    job = api_rq.call("worker.convert_image", data)
    if not job:
        return get_response_error_formatted(401, {'error_msg': "Failed reaching the services."})

    ret = {'status': 'success', 'job_id': job.id}
    return get_response_formatted(ret)


@blueprint.route('/job/<string:job_id>', methods=['GET'])
def api_get_job_state(job_id):
    """Returns the state of a job_id and it's result
    ---
    tags:
      - media
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
        description: Returns if the job has completed, and/or the address of the result
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
        schema:
          id: Job ID
          type: object
          properties:
            error_msg:
              type: string

    """
    job = api_rq.fetch_job(job.id)

    status = job.get_status()
    if status == "failed":
        return get_response_error_formatted(
            500, {'error_msg': "There was some problem performing this task, please contact an administrator."})

    ret = {'status': 'success', 'job_id': job_id, 'job_status': status}
    if status == "finished":
        ret['result'] = job.result

    return get_response_formatted(ret)

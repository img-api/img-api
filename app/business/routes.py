from app.business import blueprint
from api import get_response_formatted, api_key_or_login_required
from flask import render_template
from flask_login import current_user

from api.company.models import DB_Company


@blueprint.route('/create', methods=['GET', 'POST'])
def create_business():
    """ Creates a new business """
    return render_template('create_business.html')


@blueprint.route('/', methods=['GET', 'POST'])
def show_business_list():
    """ Displays all the business which belong to this user """
    business = DB_Company.objects(username=current_user.username)
    return render_template('show_business.html', business_list=business)


@blueprint.route('/<string:username>/<string:biz_name>', methods=['GET', 'POST'])
@blueprint.route('/<string:username>/<string:biz_name>', methods=['GET', 'POST'])
def api_get_business_info(username, biz_name):
    """ Business show info
    ---
    """

    business = DB_Company.objects(username=username, safe_name=biz_name).first()
    return render_template('display_business.html', business=business)


from app.root import blueprint
from api import get_response_formatted
from flask import render_template, redirect
from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q


@blueprint.route('/test', methods=['GET', 'POST'])
def root_app_test():
    """ Returns a simple hello world used by the testing unit to check if the system works """

    return get_response_formatted({'status': 'success', 'msg': 'test_app_root'})


@blueprint.route('/', methods=['GET', 'POST'])
def root_main_render():
    """ Returns the main HTML site """
    from api.media.models import File_Tracking

    query = Q(is_public=True) & (Q(is_unlisted=False) | Q(is_unlisted=None))
    files = File_Tracking.objects(query)

    display = []

    count = 0
    for f in reversed(files):
        if f.exists():
            display.append(f)
            count += 1

            # We should limit this on the File_Tracking call
            if count > 150:
                break

    return render_template('index.html', media_files=display)


@blueprint.route('/login', methods=['GET', 'POST'])
def root_login_into_account():
    """ Shows the login and password """
    return render_template('login.html')


@blueprint.route('/create_account', methods=['GET', 'POST'])
def root_create_account():
    """ Shows the login and password """
    return render_template('create_account.html')

@blueprint.route('/favicon.ico')
def favicon():
    return redirect("/static/img-api/favicon/favicon.ico")

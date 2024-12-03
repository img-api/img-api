import binascii
import random
from datetime import datetime

import bcrypt
import validators
from api import (admin_login_required, api_key_login_or_anonymous,
                 api_key_or_login_required, get_response_error_formatted,
                 get_response_formatted, mail)
from api.galleries.models import DB_MediaList
from api.print_helper import *
from api.query_helper import build_query_from_request, mongo_to_dict_helper
from api.tools import is_api_call
from api.tools.validators import is_valid_username
from api.user import blueprint
from api.user.models import User
from flask import Response, abort, redirect, request
from flask_login import current_user, login_user, logout_user
from flask_mail import Message
from mongoengine.queryset.visitor import Q
from services.dictionary.my_dictionary import words


def get_user_from_request():

    user = None
    username = None

    if request.method == 'POST':
        form = request.json

        if 'email' not in form or form['email'] == None:
            return get_response_error_formatted(401, {'error_msg': "Please provide an email."})

        email = form['email'].strip()
        if 'username' in form:
            username = form['username'].strip()

        password = form['password']
    else:
        email = request.args.get("email").strip()
        username = request.args.get("username").strip()
        password = request.args.get("password")

    if not password:
        return get_response_error_formatted(401, {'error_msg': "Please provide a password."})

    if not email:
        return get_response_error_formatted(401, {'error_msg': "Please provide an email."})

    if email:
        email = email.strip()
        if not validators.email(email):
            username = email
        else:
            user = User.objects(email__iexact=email).first()

    if username:
        # Users tend to add extra spaces, frontend should take care of it, but the user calling the API might not write the username properly.
        username = username.strip()
        if not is_valid_username(username):
            return get_response_error_formatted(401, {'error_msg': "Sorry, please contact an admin."})

        user = User.objects(username__iexact=username).first()

    if not user:
        return get_response_error_formatted(401, {'error_msg': "Account not found!"})

    user_pass = binascii.unhexlify(user.password)
    if not bcrypt.checkpw(password.encode('utf-8'), user_pass):
        return get_response_error_formatted(
            401, {'error_msg': "Wrong user or password, please try again or create a new user!"})

    if not user.active:
        return get_response_error_formatted(401, {'error_msg': "Please wait for an admin to give you access."})

    return user


@blueprint.route('/login', methods=['GET', 'POST'])
def api_login_user():
    """Login an user into the system
    ---
    tags:
      - user
    schemes: ['http', 'https']
    deprecated: false
    parameters:
        - in: query
          name: email
          schema:
            type: string
          description: A valid email
        - in: query
          name: password
          schema:
            type: string
          description: A vaild password
    definitions:
      user:
        type: object
    definitions:
      user_file:
        type: object
    responses:
      200:
        description: Logins the user
        schema:
          id: Token callback response
          type: object
          properties:
            msg:
                type: string
            status:
                type: string
            token:
                type: string
      401:
        description: User is not authorized to perform this operation, read the error message
        schema:
          id: Login error
          type: object
          properties:
            msg:
                type: string
            status:
                type: string
    """

    user = get_user_from_request()
    if isinstance(user, Response):
        return user

    login_user(user, remember=True)

    token = user.generate_auth_token()
    return get_response_formatted({'status': 'success', 'msg': 'hello user', 'token': token})


@blueprint.route('/create', methods=['GET', 'POST'])
def api_create_user_local():
    """ User creation
    ---
    tags:
      - user
    schemes: ['http', 'https']
    deprecated: false
    parameters:
        - in: query
          name: email
          schema:
            type: string
          description: A valid email that will define username
        - in: query
          name: password
          schema:
            type: string
          description: A vaild password
    definitions:
      user:
        type: object
    responses:
      200:
        description: Returns if the user was successfully created
        schema:
          id: Standard status message
          type: object
          properties:
            msg:
                type: string
            status:
                type: string
            timestamp:
                type: string
            time:
                type: integer

    """
    from api.tools.validators import (get_validated_email, is_password_valid,
                                      is_valid_username)

    print("======= CREATE USER LOCAL =============")

    if request.method == 'POST':
        form = request.json

        if 'first_name' in form:
            first_name = form['first_name']
        else:
            first_name = ""

        if 'last_name' in form:
            last_name = form['last_name']
        else:
            last_name = ""

        email = form['email'].strip().lower()
        username = form['username'].strip().lower()
        password = form['password']
    else:
        first_name = request.args.get("first_name", "")
        last_name = request.args.get("last_name", "")

        email = request.args.get("email").strip().lower()
        username = request.args.get("username").strip()
        password = request.args.get("password")

    if first_name: first_name = first_name.strip()
    if last_name: last_name = last_name.strip()

    if len(username) < 4:
        return get_response_error_formatted(401, {'error_msg': "Your username is too short"})

    if not is_valid_username(username):
        return get_response_error_formatted(401, {'error_msg': "Your username has non valid characters"})

    if not is_password_valid(password):
        return get_response_error_formatted(401, {'error_msg': "Password has to be at least 8 characters long"})

    hashpass = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    user = User.objects(Q(username__iexact=username) | Q(email__iexact=email)).first()
    if user:
        # Our user might already been created, we check the password against the system and we return a token in case of being the same.
        if user['email'] == email and user['username'] == username:
            user_pass = binascii.unhexlify(user.password)
            if bcrypt.checkpw(password.encode('utf-8'), user_pass):
                print(" User is already on the system with this credentials, we return a token ")

                if 'Content-Type' in request.headers and request.headers['Content-Type'] == 'application/json':
                    login_user(user)
                    user.update_with_checks(request.json)

                ret = {
                    'username': username,
                    'email': email,
                    'duplicate': True,
                    'status': 'success',
                    'msg': 'You were already registered, here is our token of gratitude',
                    'user': user.serialize(),
                    'token': user.generate_auth_token()
                }

                return get_response_formatted(ret)

        return get_response_error_formatted(
            401, {'error_msg': "The username and email combination does not match this user"})

    email = get_validated_email(email)
    if isinstance(email, Response):
        return email

    user_obj = {
        'first_name': first_name,
        'last_name': last_name,
        'password': hashpass.hex(),
        'username': username,
        'email': email,

        # Active by default, we don't have validation on this system
        'active': True,
    }

    user = User(**user_obj)
    user.save()

    ret = {
        'username': username,
        'email': email,
        'status': 'success',
        'msg': 'Thanks for registering',
        'token': user.generate_auth_token(),
        'user': user.serialize()
    }
    return get_response_formatted(ret)


@blueprint.route('/mail/password_recovery', methods=['OPTIONS', 'GET', 'POST'])
@blueprint.route('/password_recovery', methods=['OPTIONS', 'GET', 'POST'])
def api_user_recovery():
    if request.method == "OPTIONS":
        # Handle preflight here, or just let Flask-CORS handle it automatically
        return '', 200

    existing_user = None
    email = None
    user = None

    if request.json:
        if ('username' in request.json):
            username = str(request.json['username'])
            user = User.objects(username=username).first()
        elif ('email' in request.json):
            possible_email = str(request.json['email'])
            user = User.objects(email=possible_email).first()

            if not user:
                user = User.objects(username=possible_email).first()

        if user:
            email = str(user.email)
            username = str(user.username)
        else:
            return get_response_error_formatted(401, {'error_msg': "Sorry, we could not find your account."})

    else:
        user_id = request.args.get("user_id")
        if user_id:
            user = User.objects(id=user_id).first()
            username = user.username
            email = user.email
        else:
            username = request.args.get("username")

        if not username and hasattr(current_user, "username"):
            user = current_user
            username = current_user.username
            email = current_user.email
        else:
            if not username:
                if ('username' in request.form):
                    username = str(request.form['username'])

                if ('email' in request.form):
                    possible_email = str(request.form['email'])
                    user = User.objects(email=possible_email).first()

                    # https://insights.securecodewarrior.com/introducing-missions-the-next-phase-of-developer-centric-security-training/
                    # Unicode vulnerability if trusting the email from the form.
                    email = str(user.email)

                print("Find user [%s][%s]" % (username, email))

            if not user and username:
                user = User.objects(username=username).first()
                if not user:
                    return get_response_error_formatted(401, {'error_msg': "Sorry, we could not find your account."})

                username = user.username
                email = str(user.email)

    if not user:
        print("User not found [%s]" % username)
        return get_response_error_formatted(401, {'error_msg': "Sorry, we could not find your account."})

    if not user.active:
        return get_response_error_formatted(
            401, {'error_msg': "Sorry, your account has not been validated yet! Please contact an admin!"})

    print("Find user [%s][%s]" % (user.username, user.email))
    token = user.generate_auth_token()

    return password_recovery_user_email(username, email, token)


def password_recovery_user_email(username, email, token):
    import socket

    from api.config import get_config_value, get_host_name

    ####################### Report ADMIN ############################
    try:
        do_not_send = request.args.get("do_not_send")

        print_y(" PASSWORD LOST REPORT " + email)

        msg = Message(' User [%s] lost the password at %s ' % (username, socket.gethostname()),
                      sender=get_config_value("MAIL_DEFAULT_SENDER"),
                      recipients=['contact@engineer.blue'])

        msg.body = "User {email} lost the password {date} \n ".format(email=email, date=datetime.now())

        if not do_not_send:
            mail.send(msg)

        ####################### SEND RECOVERY INSTRUCTIONS ############################

        print_big(" RECOVERY LINK " + email)
        msg = Message('Reset password instructions', sender=get_config_value("MAIL_DEFAULT_SENDER"), recipients=[email])

        host = get_host_name()
        protocol = request.scheme
        recovery_link = f"{protocol}://{host}/#/password_recovery?key={token}"

        msg.body = "Hi %s,\n" % username + \
            "Someone requested to reset your password, please follow the link below:.\n\n" + \
            " %s \n\n Bad boy! \n Please, don't do it again...\n Date: %s :( " % (
                recovery_link, str(datetime.now()))

        #msg.html = render_template('email/recovery.html', btn_link=recovery_link, small_header=True, username=username)

        if do_not_send:
            print_error(" DO NOT SEND MAIL ")
            return msg.html
        else:
            mail.send(msg)

    except Exception as er:
        print_exception(er, "CRASHED")
        return get_response_error_formatted(401, {'error_msg': "Failed sending email."})

    return get_response_formatted({'email': email, 'username': username})


@blueprint.route('/remove', methods=['GET', 'POST', 'DELETE'])
@api_key_or_login_required
def api_remove_user_local():
    """ An user can delete its account
    ---
    tags:
      - user
    schemes: ['http', 'https']
    deprecated: false
    parameters:
        - in: query
          name: email
          schema:
            type: string
          description: A valid email
        - in: query
          name: password
          schema:
            type: string
          description: A vaild password
    definitions:
      user:
        type: object
    responses:
      200:
        description: Returns if the user was successfully deleted
        schema:
          id: Standard status message
          type: object
          properties:
            msg:
                type: string
            status:
                type: string
    """
    print("======= DELETE USER LOCAL =============")

    if not current_user.is_authenticated:
        return get_response_error_formatted(401, {'error_msg': "Account not found."})

    if current_user.id:
        current_user.delete()
    return get_response_formatted({'status': 'success', 'msg': 'user deleted'})


@blueprint.route('/token', methods=['GET'])
@api_key_or_login_required
def get_auth_token():
    """ Gets a token that an user can user to upload and perform operations.

    ---
    tags:
      - user
    schemes: ['http', 'https']
    deprecated: false
    parameters:
        - in: query
          name: token
          schema:
            type: string
          description: (Optional) If there is a token on the call, it will check if it is validity

    definitions:
      token:
        type: object
    responses:
      200:
        description: Returns the user token
        schema:
          id: Token
          type: object
          properties:
            token:
                type: string
    """

    token = request.args.get("key")
    if not token:
        token = current_user.generate_auth_token()
        return get_response_formatted({'token': token, 'username': current_user.username})

    user = User.verify_auth_token(token)
    if isinstance(user, Response):
        return user

    login_user(user, remember=True)
    return get_response_formatted({
        'token': token,
        'username': user.username,
        'status': 'success',
        'first_name': user.first_name,
        'last_name': user.last_name
    })


@blueprint.route('/get/<string:user_id>', methods=['GET'])
@api_key_login_or_anonymous
def api_get_user_by_username(user_id):
    """ Returns the current user being logged in
    ---
    tags:
      - user
    schemes: ['http', 'https']
    deprecated: false
    parameters:
        - in: query
          name: username
          schema:
            type: string
          description: Username, you can use no user name, that would be you. Or an alias called "me" that will also be you.
    definitions:
      user_file:
        type: object
    responses:
      200:
        description: Returns the username in a message in a serialized form
        schema:
          id: Standard status message
          type: object
          properties:
            username:
                type: string
      401:
        description: There is a problem with this user
        schema:
          id: Login error
          type: object
          properties:
            msg:
                type: string
            status:
                type: string
    """

    if not user_id or user_id == "me":
        if not current_user.is_authenticated:
            return get_response_error_formatted(401, {'error_msg': "Please login or create an account."})

        if not current_user or not current_user.username:
            return get_response_error_formatted(401, {'error_msg': "Account not found."})

        current_user.check_in_usage()
        return get_response_formatted({'user': current_user.serialize()})

    user = User.objects(username__iexact=user_id).first()
    if not user or not user.username:
        return get_response_error_formatted(401, {'error_msg': "Account not found."})

    return get_response_formatted({'user': user.serialize()})


@blueprint.route('/get', methods=['GET'])
def api_get_current_user():
    return api_get_user_by_username(None)


def generate_random_name():
    """ Generates a random name so we can use it for the anonymous user.
        This name should come from a dictionary like 3words
    """

    l = len(words)

    my_user_name = ""
    while not my_user_name:
        for i in range(0, 3):
            r = random.randint(0, l - 1)
            if i != 0:
                my_user_name += "_"

            my_user_name += words[r]

        if User.objects(username=my_user_name).first():
            print("Found collision " + my_user_name)
            my_user_name = ""

    print("Your user name " + my_user_name)
    return my_user_name.upper()


@blueprint.route('/get_random_name', methods=['GET'])
def api_get_random_name():
    return get_response_formatted({'username': generate_random_name()})


def generate_random_user():
    """ We generate a random user for files which are going to be anonymous
        The user will be able to modify the files until they delete their cookies
    """

    random_name = generate_random_name()
    password = random_name + str(datetime.now())
    user_obj = {
        'password': bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).hex(),
        'username': random_name,
        'email': random_name + "@img-api.com",
        'is_anon': True,
        'active': True,
    }

    user = User(**user_obj)
    user.save()

    login_user(user, remember=True)
    return user


@blueprint.route('/logout', methods=['GET', 'POST'])
def api_user_logout():
    """ User logout, remove cookies
    ---
    tags:
      - user
    schemes: ['http', 'https']
    deprecated: false
    definitions:
      user:
        type: object
    responses:
      200:
        description: Just logs out the user
    """

    if not current_user.is_authenticated:
        return get_response_error_formatted(401, {'error_msg': "Please login or create an account."})

    logout_user()

    if is_api_call():
        return get_response_formatted({'status': 'success', 'msg': 'user logged out'})

    return redirect("/")


@blueprint.route('/admin/query', methods=['GET', 'POST'])
@api_key_or_login_required
@admin_login_required
def api_user_get_query():
    users = build_query_from_request(User, global_api=True)
    ret = {'users': users}
    return get_response_formatted(ret)


@blueprint.route('/admin/get/<string:username>', methods=['GET', 'POST'])
@api_key_or_login_required
@admin_login_required
def api_user_get_query_only(username):
    if username == "ALL":
        users = User.objects()
        return get_response_formatted({'users': users})

    users = User.objects(username=username)
    return get_response_formatted({'users': users})


@blueprint.route('/admin/set/<string:username>/<string:my_key>', methods=['GET', 'POST'])
@api_key_or_login_required
@admin_login_required
def admin_set_user_info(username, my_key):
    user = User.objects(username=username).first()
    if not user:
        return get_response_error_formatted(400, {'error_msg': "Username doesn't exist."})

    value = request.args.get("value", None)
    if not value and 'value' in request.json:
        value = request.json['value']

    if value == None:
        return get_response_error_formatted(400, {'error_msg': "Wrong parameters."})

    if not user.set_key_value(my_key, value, is_admin=True):
        return get_response_error_formatted(400, {'error_msg': "Something went wrong saving this key."})

    ret = {"user": user.serialize()}
    return get_response_formatted(ret)


@blueprint.route('/admin/rm/<string:username>', methods=['GET', 'POST'])
@api_key_or_login_required
@admin_login_required
def api_user_remove_user(username):
    users = User.objects(username=username)
    ret = {'users': users}
    users.delete()
    return get_response_formatted(ret)


@blueprint.route('/media/<string:media_id>/<string:action>/<string:my_list>', methods=['GET'])
@api_key_or_login_required
def api_set_this_media_into_an_action(media_id, action, my_list):
    """ Performs an action for a particular media in a list.
        This can be, add it to favourites, or likes, dislikes, add it to a playlist...
    ---
    tags:
      - user
    schemes: ['http', 'https']
    deprecated: false
    parameters:
        - in: query
          name: media_id
          schema:
            type: string
          description: The media

        - in: query
          name: action
          schema:
            type: string
          description: append, remove, toggle

        - in: query
          name: my_list
          schema:
            type: string
          description: Internal media list

    definitions:
      user_file:
        type: object
    """
    from api.media.routes import api_set_media_private_posts_json

    if action == "toggle" and my_list == "is_public":
        return api_set_media_private_posts_json(media_id, action)

    ret = current_user.action_on_list(media_id, action, my_list)
    return get_response_formatted(ret)


@blueprint.route('/<string:username>/list/get', methods=['GET'])
@api_key_login_or_anonymous
def api_get_all_the_lists_by_username(username):
    """ Gets all the list of media lists this an user has. It is a private call for this user
    ---
    tags:
      - user
    schemes: ['http', 'https']
    deprecated: false
    definitions:
      user_file:
        type: object
    responses:
      200:
        description: Returns a list of lists
    """

    ret = None
    if current_user.is_authenticated:
        if username == 'me':
            username = current_user.username

        if current_user.username == username:
            ret = current_user.galleries.get_every_media_list(username)

    if not ret:
        if username == "me":
            return get_response_error_formatted(404, {'error_msg': "Please create an account."})

        user = User.objects(username__iexact=username).first()
        if not user or not user.is_public:
            return get_response_error_formatted(404, {'error_msg': "User not found."})

        ret = user.galleries.get_every_media_list(username)

    if False:
        ret['galleries'].pop('favs', None)

    return get_response_formatted(ret)


@blueprint.route('/<string:username>/list/<string:list_id>/<string:action>/<string:my_param>/<string:my_value>',
                 methods=['GET'])
@blueprint.route('/<string:username>/list/<string:list_id>/<string:action>/<string:my_param>', methods=['GET'])
@blueprint.route('/<string:username>/list/<string:list_id>/<string:action>', methods=['GET', 'DELETE'])
@api_key_login_or_anonymous
def api_actions_on_list(username, list_id, action, my_param=None, my_value=None):
    """ Performs an action for a list
    ---
    tags:
      - user
    schemes: ['http', 'https']
    deprecated: false
    parameters:
        - in: query
          name: username
          schema:
            type: string
          description: Username to perform an action. An anonymous user can ask for public media lists

        - in: query
          name: list_id
          schema:
            type: string
          description: The media

        - in: query
          name: action
          schema:
            type: string
          description: create, remove, get, add, set

        - in: query
          name: no_populate
          schema:
            type: string
          description: Do not add all the media_files and leave the media_list

    definitions:
      user_file:
        type: object
    responses:
      200:
        description: Returns a list of media_files
      400:
        description: The list is not found
      401:
        description: The list is private to that particular user
    """

    from api.media.routes import (api_get_user_photostream,
                                  api_populate_media_list)

    if list_id == "undefined":
        return get_response_error_formatted(400, {'error_msg': "Wrong frontend."})

    if current_user.is_authenticated:
        if username == 'me' or current_user.username == username:
            if action == 'remove':
                res = current_user.media_list_remove(list_id)
                return get_response_formatted(res)

            if action == 'set':
                if not my_value: my_value = True
                ret = current_user.set_on_list(list_id, my_param, my_value)
                return get_response_formatted(ret)

            if action == 'unset':
                # Removes the parameter from the list
                ret = current_user.unset_on_list(list_id, my_param)
                return get_response_formatted(ret)

    if action == 'get':

        # We have the special category "stream" which is the photo stream of the user.
        # That will be their public photos if you are a third party user, or all your pictures if it is you.
        if list_id == "stream":
            return api_get_user_photostream(username)

        # Galleries owned by you will display everything
        if current_user.is_authenticated and (username == 'me' or current_user.username == username):
            ret = current_user.galleries.media_list_get(list_id, my_param)
        else:
            # Galleries owned by a third pary will only display public facing pictures
            user = User.objects(username__iexact=username).first()
            if not user:
                return get_response_error_formatted(404, {'error_msg': "User not found."})

            ret = user.galleries.media_list_get(list_id, my_param)

        # We populate the list with results, and not only media IDs
        # The user might want to get a clean view without extra information, to maybe display only the tile.
        populate = not request.args.get("no_populate", False)
        if populate:
            media_list = [media['media_id'] for media in ret['media_list']]
            if media_list:
                ret.update(api_populate_media_list(username, media_list, ret['is_order_asc']))

        return get_response_formatted(ret)

    return get_response_error_formatted(400, {'error_msg': "Wrong parameters."})


@blueprint.route('/list/get_by_id/<string:list_id>/<string:image_type>', methods=['GET'])
@blueprint.route('/list/get_by_id/<string:list_id>', methods=['GET'])
@api_key_login_or_anonymous
def api_get_by_list_id(list_id, image_type=None):
    """ Gets all the list of media this list has, if it is public
    ---
    tags:
      - user
    schemes: ['http', 'https']
    deprecated: false
    definitions:
      user_file:
        type: object
    responses:
      200:
        description: Returns a the list given by id if it is public or you are the owner
      404:
        description: Missing gallery
      401:
        description: Gallery is not public and it is not yours

    """
    from api.media.routes import api_populate_media_list

    the_list = DB_MediaList.objects(pk=list_id).first()
    if not the_list:
        return abort(404, "Missing Gallery")

    if current_user.is_authenticated and the_list.username != current_user.username:
        if not the_list.is_public:
            return abort(401, "Unauthorized")

    ret = mongo_to_dict_helper(the_list)

    arr = the_list.get_as_list()
    if image_type == "random":
        arr = [random.choice(arr)]

    if request.args.get("populate", False):
        ret.update(api_populate_media_list(the_list.username, arr, the_list.is_order_asc))

    return get_response_formatted(ret)


@blueprint.route('/list/get', methods=['GET'])
@api_key_or_login_required
def api_get_all_the_lists():
    """ Gets all the list of media lists this user has. It is a private call for this user
    ---
    tags:
      - user
    schemes: ['http', 'https']
    deprecated: false
    definitions:
      user_file:
        type: object
    responses:
      200:
        description: Returns a list of lists
    """

    if not current_user.is_authenticated:
        return abort(401, "Please login or create an account to create galleries")

    ret = current_user.galleries.get_every_media_list(current_user.username)

    if False:
        ret['galleries'].pop('favs', None)

    return get_response_formatted(ret)


@blueprint.route('/list/create', methods=['POST'])
@api_key_or_login_required
def api_create_a_new_list():
    """ Gets all the list of media lists this user has. It is a private call for this user
    ---
    tags:
      - user
    schemes: ['http', 'https']
    deprecated: false
    definitions:
      user_file:
        type: object
    responses:
      200:
        description: Returns the created gallery
      409:
        description: The gallery already exists and there is a conflict
    """

    g = current_user.galleries

    json = request.json
    title = json['title']
    gallery_name = g.get_safe_gallery_name(title)
    if len(gallery_name) <= 2:
        return get_response_error_formatted(400, {'error_msg': "Gallery name has to be longer than that"})

    ret = g.exists(gallery_name)
    print_b("Creating " + gallery_name)

    if ret:
        print_r("Duplicated")
        media_list = current_user.get_media_list(gallery_name, raw_db=True)
        media_list.update_with_checks(json)

        ret = {'galleries': [media_list.serialize()], 'username': current_user.username, 'duplicated': True}
        return ret

    media_list = g.create(current_user.username, gallery_name, json)

    if not media_list:
        return get_response_error_formatted(400, {'error_msg': "Wrong parameters."})

    ret = {"galleries": [media_list.serialize()], 'username': current_user.username}

    current_user.save(validate=False)
    return get_response_formatted(ret)


@blueprint.route('/list/update', methods=['POST'])
@api_key_or_login_required
def api_update_a_list():
    """ Updates the list information, we only accept calls from this user
    ---
    tags:
      - user
    schemes: ['http', 'https']
    deprecated: false
    definitions:
      user_file:
        type: object
    responses:
      200:
        description: Returns the updated library
      401:
        description: User cannot update this library
    """

    ret = current_user.galleries.update(request.json)
    current_user.save(validate=False)
    ret['username'] = current_user.username

    return get_response_formatted(ret)


@blueprint.route('/list/remove/<string:list_id>', methods=['POST'])
@api_key_or_login_required
def api_remove_a_list(list_id):
    """ Remove a media list
    ---
    tags:
      - user
    schemes: ['http', 'https']
    definitions:
      user_file:
        type: object
    responses:
      200:
        description: Deletes a media
    """

    res = current_user.media_list_remove(list_id)
    return get_response_formatted(res)


@blueprint.route('/list/clear', methods=['GET', 'DELETE'])
@api_key_or_login_required
def api_delete_all_the_lists():
    """ Deletes every list that this user has. Mainly for testing purposes
    ---
    tags:
      - user
    schemes: ['http', 'https']
    deprecated: false
    definitions:
      user_file:
        type: object
    """

    ret = current_user.galleries.clear_all(current_user.username)
    current_user.save()
    return get_response_formatted(ret)


@blueprint.route('/set/<string:my_key>', methods=['GET', 'POST'])
@api_key_or_login_required
def set_user_info(my_key):
    """ Sets this user variable

    ---
    tags:
      - user
    schemes: ['http', 'https']
    deprecated: false
    parameters:
        - in: query
          name: my_key
          schema:
            type: string
          description: Key to set a value

    definitions:
      my_key:
        type: A valid key, like is_public, or something on 'my_' which is available for the user to set
    responses:
      200:
        description: Returns the user token
        schema:
          id: Token
          type: object
          properties:
            token:
                type: string
    """
    from api.tools.validators import is_password_valid

    value = request.args.get("value", None)
    if not value and 'value' in request.json:
        value = request.json['value']

    if value == None:
        return get_response_error_formatted(400, {'error_msg': "Wrong parameters."})

    if my_key == "password":
        if not is_password_valid(value):
            return get_response_error_formatted(401, {'error_msg': "Password has to be at least 8 characters long"})

        value = bcrypt.hashpw(value.encode('utf-8'), bcrypt.gensalt()).hex()
        current_user.update(**{"password": value})

        ret = {"user": current_user.serialize()}
        return get_response_formatted(ret)

    if isinstance(value, str):
        value = clean_html(value)

    if not current_user.set_key_value(my_key, value):
        return get_response_error_formatted(400, {'error_msg': "Something went wrong saving this key."})

    ret = {"user": current_user.serialize()}
    return get_response_formatted(ret)

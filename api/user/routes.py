import bcrypt
import binascii
import datetime
import validators

from api.user import blueprint

from api import get_response_formatted, get_response_error_formatted, api_key_or_login_required

from flask import jsonify, request, Response, redirect
from flask_login import current_user, login_user, logout_user
from api.tools import generate_file_md5, ensure_dir, is_api_call

from .models import User

from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q


def get_user_from_request():
    user = None
    username = None

    if request.method == 'POST':
        form = request.json

        email = form['email']
        if 'username' in form:
            username = form['username']

        password = form['password']
    else:
        email = request.args.get("email")
        username = request.args.get("username")
        password = request.args.get("password")

    if not password:
        return get_response_error_formatted(401, {'error_msg': "Please provide a password."})

    if not email:
        return get_response_error_formatted(401, {'error_msg': "Please provide an email."})

    if username:
        user = User.objects(username=username).first()
    else:
        user = User.objects(email=email).first()

    if not user:
        return get_response_error_formatted(401, {'error_msg': "Please create an account."})

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


def split_addr(emailStr, encoding):
    import re

    regexStr = r'^([^@]+)@[^@]+$'
    matchobj = re.search(regexStr, emailStr)
    if not matchobj is None:
        print("EMAIL ADDRESS " + matchobj.group(1))
    else:
        print("Did not match")
        return None, None

    return [matchobj.group(0), matchobj.group(1)]


def sanitize_address(addr, encoding):
    """
    Format a pair of (name, address) or an email address string.
    """
    from email.utils import parseaddr
    from email.errors import InvalidHeaderDefect, NonASCIILocalPartDefect
    from email.header import Header
    from email.headerregistry import Address

    if not isinstance(addr, tuple):
        addr = parseaddr(addr)
    nm, addr = addr
    localpart, domain = None, None
    nm = Header(nm, encoding).encode()

    try:
        try:
            addr.encode('ascii')
        except UnicodeEncodeError:  # IDN or non-ascii in the local part
            localpart, domain = split_addr(addr, encoding)

        # An `email.headerregistry.Address` object is used since
        # email.utils.formataddr() naively encodes the name as ascii (see #25986).
        if localpart and domain:
            address = Address(nm, username=localpart, domain=domain)
            return str(address)

        try:
            address = Address(nm, addr_spec=addr)
        except (InvalidHeaderDefect, NonASCIILocalPartDefect):
            localpart, domain = split_addr(addr, encoding)
            address = Address(nm, username=localpart, domain=domain)

    except Exception as err:
        print(" Address not valid " + str(err))
        return None

    return str(address)


def check_email(email):
    # Regex test
    import re
    if not email:
        return False

    # As it is, it will support more than one plus in the string, FIX is required
    match = re.match('^[_a-z0-9-\+]+(\.[_a-z0-9-\+]+)*@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,4})$', email)
    if match == None:
        return False

    return True


def get_validated_email(email):
    # https://stackoverflow.com/questions/8022530/how-to-check-for-valid-email-address

    if not validators.email(email):
        return get_response_error_formatted(400, {'error_msg': "Please provide a valid email"})

    try:
        if not email or len(email) == 0:
            return get_response_error_formatted(400, {'error_msg': "Please provide a valid email"})

        email_clean = sanitize_address(email, 'iso-8859-1')
        if not email_clean or not check_email(email_clean):
            return get_response_error_formatted(400,
                                                {'error_msg': "Please provide a valid email " + email + " is no valid"})

        print(" Email after sanitize_address " + str(email_clean))
        return email_clean

    except Exception as e:
        return get_response_error_formatted(400,
                                            {'error_msg': "Please provide a valid email " + email + " is no valid"})

    return None


def is_password_valid(password):
    """ Check password policies
        We should check a dictionary and length
    """

    if len(password) < 8:
        return False

    return True


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

    print("======= CREATE USER LOCAL =============")

    if request.method == 'POST':
        form = request.json
        first_name = form['first_name']
        last_name = form['last_name']

        email = form['email']
        username = form['username']
        password = form['password']
    else:
        first_name = request.args.get("first_name")
        last_name = request.args.get("last_name")

        email = request.args.get("email")
        username = request.args.get("username")
        password = request.args.get("password")

    if not is_password_valid(password):
        return get_response_error_formatted(401, {'error_msg': "Invalid password"})

    hashpass = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    user = User.objects(Q(username=username) | Q(email=email)).first()
    if user:
        # Our user might already been created, we check the password against the system and we return a token in case of being the same.
        if user['email'] == email and user['username'] == username:
            user_pass = binascii.unhexlify(user.password)
            if bcrypt.checkpw(password.encode('utf-8'), user_pass):
                print(" User is already on the system with this credentials, we return a token ")

                ret = {
                    'username': username,
                    'email': email,
                    'duplicate': True,
                    'status': 'success',
                    'msg': 'You were already registered, here is our token of gratitude',
                    'token': user.generate_auth_token()
                }

            return get_response_formatted(ret)

        return get_response_error_formatted(401, {'error_msg': "User already on the system, would you like to login?"})

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
        'token': user.generate_auth_token()
    }
    return get_response_formatted(ret)


@blueprint.route('/remove', methods=['GET', 'POST'])
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

    user = get_user_from_request()
    if isinstance(user, Response):
        return user

    user.delete()
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
        return get_response_formatted({'token': token})

    user = User.verify_auth_token(token)
    if isinstance(user, Response):
        return user

    login_user(user, remember=True)
    return get_response_formatted({'token': token, 'user': user.username, 'status': 'success'})


@blueprint.route('/get', methods=['GET'])
@api_key_or_login_required
def api_get_current_user():
    """ Returns the current user being logged in
    ---
    tags:
      - user
    schemes: ['http', 'https']
    deprecated: false
    definitions:
      user:
        type: object
    definitions:
      user_file:
        type: object
    responses:
      200:
        description: Returns if the file was successfully uploaded
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

    if not hasattr(current_user, 'username'):
        return get_response_error_formatted(401, {'error_msg': "Please login or create an account."})

    if not current_user or not current_user.username:
        return get_response_error_formatted(401, {'error_msg': "Please create an account."})

    return get_response_formatted({'user': current_user.username})


def generate_random_name():
    """ Generates a random name so we can use it for the anonymous user.
        This name should come from a dictionary like 3words
    """

    random_name = str(datetime.datetime.now())
    #
    return random_name

def generate_random_user():
    """ We generate a random user for files which are going to be anonymous
        The user will be able to modify the files until they delete their cookies
    """

    random_name = generate_random_name()
    user_obj = {
        'password': bcrypt.hashpw(random_name.encode('utf-8'), bcrypt.gensalt()).hex(),
        'username': random_name,
        'email': random_name[:24] + "@img-api.com",
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

    if not hasattr(current_user, 'username'):
        return get_response_error_formatted(401, {'error_msg': "Please login or create an account."})

    logout_user()

    if is_api_call():
        return get_response_formatted({'status': 'success', 'msg': 'user logged out'})

    return redirect("/")

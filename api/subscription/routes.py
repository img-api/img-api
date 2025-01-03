import socket
from datetime import datetime, timedelta

import mistune
import requests
from api import get_response_formatted, mail
from api.config import (get_api_AI_service, get_api_entry, get_config_value,
                        is_api_development)
from api.print_helper import *
from api.prompts.models import DB_UserPrompt
from api.query_helper import *
from api.subscription import blueprint
from api.user.models import User
from flask_login import AnonymousUserMixin, current_user
from flask_mail import Mail, Message
from mongoengine import *
from mongoengine.errors import ValidationError


def generate_email_subject(email_data):
    """
    Generates an email subject by combining several items from the given JSON data.

    Args:
        email_data (dict): JSON-like dictionary containing email data.

    Returns:
        str: Generated email subject.
    """
    # Extract tools list from the data
    try:
        tools = email_data.get("tools", [])

        # Initialize variables
        classification = ""
        title = ""
        defcon_alert = ""
        sentiment = ""

        # Loop through tools to extract relevant arguments
        for tool in tools:
            arguments = tool.get("function", {}).get("arguments", {})

            # Get classification from set_article_information
            if "classification" in arguments:
                classification = arguments.get("classification")

            # Get title from set_article_information
            if "title" in arguments:
                title = arguments.get("title")

            # Get defcon_alert from send_portfolio_alert
            if "defcon_alert" in arguments:
                defcon_alert = arguments.get("defcon_alert")

            # Get sentiment from set_sentiment_icon
            if "sentiment" in arguments:
                sentiment = arguments.get("sentiment")

        # Build the email subject
        subject_parts = []
        if classification:
            subject_parts.append(f"[{classification}]")
        if title:
            subject_parts.append(title)
        if defcon_alert:
            subject_parts.append(f"({defcon_alert})")
        if sentiment:
            subject_parts.append(f"- Sentiment: {sentiment.capitalize()}")

        # Join parts to form the subject line
        return " ".join(subject_parts)
    except Exception as e:
        print_exception(e, "CRASHED")

    now = datetime.now()
    return "Portfolio Report: " + now.strftime("%B %Y")


def send_subscription_user_email(db_user, subject, email):
    try:
        msg = Message(subject,
                      sender=get_config_value("MAIL_DEFAULT_SENDER"),
                      recipients=[db_user.email],
                      bcc=['contact@engineer.blue'])

        msg.body = email

        html = mistune.html(email)
        header = '<span style="font-family: Arial, Helvetica, sans-serif; font-size: 12px; color: #111;">'
        footer = '</span>'

        html = header + html + footer

        #msg.html = render_template('email/recovery.html', btn_link=recovery_link, small_header=True, username=username)
        msg.html = html

        mail.send(msg)

    except Exception as er:
        print_exception(er, "CRASHED")


def api_create_prompt_subscription_email(db_user, articles_content):
    from api.prompts.routes import cut_string

    # Todo, get the latest prompt. The UI needs to update too.

    prompt = "Write an email for the user explaining the information from the articles and their portfolio.\n"
    prompt += "Your output is a final email content that the user will receive, it's not a template and don't include the subject.\n"
    prompt += "Use markdown and unicode emojis and icons as extra output for the text to be well formatted."

    system = "Today is " + str(datetime.now().strftime("%Y/%m/%d, %H:%M")) + "\n"
    system += "The user is " + db_user.first_name + " " + db_user.last_name + "\n"
    system += "Your name is TOTHEMOON, you are an expert system that can provide financial advice due regulations in the country.\n"


    assistant = cut_string(articles_content, 256000)

    data = {
        'type': 'email_prompt',
        'prompt': prompt,
        'system': system,
        'assistant': assistant,
        'status': "WAITING_AI",
        'use_markdown': True,
        'username': db_user.username,
        'hostname': socket.gethostname()
    }

    if is_api_development():
        data['dev'] = True

    db_prompt = DB_UserPrompt(**data)
    db_prompt.save(is_admin=True)

    data['id'] = str(db_prompt.id)
    data['prefix'] = "1_SUBS_" + db_prompt.username
    data['callback_url'] = get_api_entry() + "/subscription/ai_callback"
    data['priority'] = 2

    try:
        response = requests.post(get_api_AI_service(), json=data)
        response.raise_for_status()

        json_response = response.json()
        print_json(json_response)

        db_prompt.update(**{
            'raw': json_response,
            'ai_upload_date': datetime.now(),
            'ai_queue_size': json_response['queue_size']
        })

        return json_response
    except Exception as e:
        print_exception(e, "CRASH READING RESPONSE")

    return {}


def api_subscription_process_user(db_user):
    from api.news.routes import get_portfolio_query
    from api.prompts.routes import (api_create_content_from_news,
                                    api_create_content_from_tickers)

    print_b(" Process user " + db_user.username)

    last_process = datetime.now()

    db_user.update(**{'last_email_date': last_process})

    extra_args = {'reversed': 1}
    news, tkrs = get_portfolio_query(my_args=extra_args, username=db_user.username)

    if len(tkrs) == 0:
        return

    tickers = api_create_content_from_tickers(tkrs)
    content = api_create_content_from_news(news)

    print("CONTENT SIZE: " + str(len(content)))

    api_create_prompt_subscription_email(db_user, tickers + content)
    return db_user


def check_subscription_status():
    try:
        results = User.objects()
        for obj in results:
            if not obj.subscription:
                continue

            print_b(obj.username + " " + obj.subscription.status + " " + obj.current_subscription)

            print_b(" Last processed " + str(obj.last_email_date))

            # Reset process
            if request.args.get("forced", None):
                last_process = datetime.today() - timedelta(days=8)
                obj.update(**{'last_email_date': last_process})

                if len(obj.list_payments) > 1:
                    obj.update(**{'list_payments': [obj.list_payments[-1]]})

    except ValidationError as e:
        print(f"Offending object found: {obj.id}, Error: {e}")
        return obj.id  # Return the offending object's ID
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def get_raw_query(last_process):
    raw = {
        "$or": [{
            "last_email_date": {
                "$lt": last_process
            }
        }, {
            "last_email_date": {
                "$exists": False
            }
        }, {
            "last_email_date": None
        }]
    }
    return raw


@blueprint.route('/process', methods=['GET', 'DELETE'])
def api_process_user_subscription():
    from api.query_helper import mongo_to_dict_helper

    tier_2 = []

    check_subscription_status()

    # Tier 2 Process
    last_process = datetime.today() - timedelta(days=7)
    user_list = User.objects(current_subscription="tier2_monthly",
                             subscription__status="active",
                             __raw__=get_raw_query(last_process))
    for user in user_list:
        tier_2.append(api_subscription_process_user(user))

    # Tier 3 Process
    tier_3 = []
    last_process = datetime.today() - timedelta(days=1)
    user_list = User.objects(current_subscription="tier3_monthly",
                             subscription__status="active",
                             __raw__=get_raw_query(last_process))

    for user in user_list:
        tier_3.append(api_subscription_process_user(user))

    if current_user.is_authenticated and current_user.username == "admin":
        return get_response_formatted({'tier2': tier_2, 'tier3': tier_3})

    return get_response_formatted({"fruit": "banana"})


@blueprint.route('/ai_callback', methods=['GET', 'POST'])
#@api_key_or_login_required
#@admin_login_required
def api_subscription_prompt_callback_ai_summary():
    json = request.json

    if 'id' not in json:
        return get_response_error_formatted(400, {'error_msg': "An id is required"})

    db_prompt = DB_UserPrompt.objects(id=json['id']).first()

    if not db_prompt or 'type' not in json:
        print_r("PROMPT FAILED UPDATING AI " + json['id'])
        return get_response_formatted({})

    print_b(" NEWS AI_CALLBACK " + json['id'] + " " + str(db_prompt.prompt))

    update = {}

    t = json['type']
    if t == 'dict':
        tools = json['dict']
        ai_summary = json['ai_summary']
        update = {'ai_summary': ai_summary, 'tools': tools}

    if t == 'email_prompt':
        update = {'ai_summary': json['result']}

    update['last_visited_date'] = datetime.now()
    update['last_visited_verbose'] = datetime.now().strftime("%Y/%m/%d, %H:%M:%S")

    if is_api_development():
        update['dev'] = True

    update['status'] = "PROCESSED"

    if 'raw' in json:
        update['raw'] = json['raw']

    if 'raw_tools' in json:
        update['raw_tools'] = json['raw_tools']

    db_user = User.objects(username=db_prompt.username).first()

    if db_user:
        subject = generate_email_subject(update)
        send_subscription_user_email(db_user, subject, update['ai_summary'])

    db_prompt.update(**update, is_admin=True)

    ret = {}
    return get_response_formatted(ret)

import socket
from datetime import datetime, timedelta

import mistune
import requests
from api import cleanup_for_email, get_response_formatted, mail
from api.company.models import DB_Company
from api.config import (get_api_AI_service, get_api_entry, get_config_sender,
                        get_config_value, get_host_name, is_api_development)
from api.news.models import DB_News
from api.print_helper import *
from api.prompts.models import DB_UserPrompt
from api.query_helper import *
from api.subscription import blueprint
from api.subscription.models import DB_Subscription
from api.user.models import User
from bson.objectid import ObjectId
from flask import Flask, json, jsonify, redirect, request
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


def get_update_param(update, key, default=None):
    """ We will deprecate this eventually and hide better the raw AI function calls """
    try:
        return update['AI'][key]
    except:
        pass

    try:
        for function in update['tools']:
            if key in function['function']['arguments']:
                return function['function']['arguments'][key]
    except:
        pass

    return default


def generate_links_email(update, email):
    try:
        company_list = get_update_param(update, "company_list", [])
        cleanup = []
        for c in company_list:
            cleanup.append(DB_Company.get_safe_name(c))

        db_comps = DB_Company.objects(safe_name__in=cleanup)
        for c in db_comps:
            print(" FOUND COMPANY " + c.long_name)
            # Write code to replace
            # email = email.replace(ticker, f"[{c.get_primary_ticker()}](https://headingtomars.com/ticker/{c.get_primary_ticker()})")

        ticker_list = get_update_param(update, "tickers_list", [])

        for ticker in ticker_list:
            db_comps = DB_Company.objects(exchange_tickers__endswith=":" + ticker)
            for c in db_comps:
                print(" FOUND COMPANY " + c.long_name)
                email = email.replace(
                    ticker, f"[{c.get_primary_ticker()}](https://headingtomars.com/ticker/{c.get_primary_ticker()})")

    except Exception as e:
        print_exception(e, "CRASH")

    return email


def send_subscription_user_email(db_user, id, subject, email):

    try:
        bcc = None
        if not db_user.is_admin:
            bcc = ['contact@engineer.blue']

        msg = Message(cleanup_for_email(subject.strip()),
                      sender=get_config_sender(),
                      recipients=[cleanup_for_email(db_user.email)],
                      bcc=bcc)

        msg.body = email.strip()

        html = mistune.html(email)
        header = '<span style="font-family: Arial, Helvetica, sans-serif; font-size: 12px; color: #111;">'
        footer = '</span>'

        html = header + html + footer

        link_text = "View on web"

        link = get_api_entry() + "/subscription/redirect/" + id
        html += f"<hr ref_id='{ id }'><h4><a ref_id='{ id }' href='{ link }'>{ link_text }</a></h4>"

        msg.html = html.strip()

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
    system += "Don't mention about the value of the stocks or the number of shares since we don't have that information if it not specified.\n"

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
        },
                         is_admin=True)

    except Exception as e:
        print_exception(e, "CRASH READING RESPONSE")

    return data, db_prompt


def api_subscription_process_user(db_user, test=False):
    from api.news.routes import get_portfolio_query
    from api.prompts.routes import (api_create_content_from_news,
                                    api_create_content_from_tickers)

    print_b(" Process user " + db_user.username)

    last_process = datetime.now()

    if not request.args.get("forced", test):
        db_user.update(**{'last_email_date': last_process})

    # Create a cache for our subscription duties.
    db_subs = DB_Subscription.objects(username=db_user.username).first()
    if not db_subs:
        data = {'username': db_user.username}
        db_subs = DB_Subscription(**data)
        db_subs.save()

    if test: print_json(db_subs)

    extra_args = {'reversed': 1}

    db_prompt = None
    if db_subs and 'last_prompt_id' in db_subs:
        db_prompt = DB_UserPrompt.objects(id=db_subs['last_prompt_id']).first()

        if db_prompt and 'ai_summary' not in db_prompt:
            print_r("THERE IS NO AI_SUMMARY YET")
            return

    # We create only the incremental from the previous call and we add the content from the last email
    # to the assistant so it knows what was the previous conversation.
    if 'last_processed_news_id' in db_subs:
        lnews = db_subs['last_processed_news_id']

        print_b("SUB: " + lnews)

        if not request.args.get("forced", None):
            extra_args['id__gt'] = ObjectId(lnews)

    news, tkrs = get_portfolio_query(my_args=extra_args, username=db_user.username)

    if len(tkrs) == 0 or len(news) == 0:
        print_r(" NO NEWS SINCE LAST UPDATE ")
        return

    try:
        last_processed_news_id = str(news[-1].id)

        if not request.args.get("forced", False):
            db_subs.update(**{'last_processed_news_id': last_processed_news_id})

    except Exception as e:
        print_exception(e, "CRASH")

    tickers = api_create_content_from_tickers(tkrs)

    if db_prompt:
        tickers += f"Previous email: { db_prompt['ai_summary'] }\n"

    content = api_create_content_from_news(news)

    print("CONTENT SIZE: " + str(len(content)))

    email, db_prompt = api_create_prompt_subscription_email(db_user, tickers + content)

    if db_prompt:
        db_subs.update(**{'last_prompt_id': str(db_prompt.id)})

    ids = []
    for n in news:
        my_date = str(n.creation_date.strftime("%Y/%m/%d"))
        ids.append({'id': str(n.id), 'date': my_date})

    if test:
        news_title = []
        for n in news:
            news_title.append({
                'id': str(n.id),
                'title': n.source_title,
                'date': timestamp_get_verbose_date(n.creation_date)
            })

        return {
            'last_processed_news_id': last_processed_news_id,
            'ids': ids,
            'username': db_user.username,
            'news': news_title,
            'email': {
                'tickers': tickers,
                'content': content,
                'email': email
            }
        }

    return {'username': db_user.username, 'news': news}


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
                #last_process = datetime.today() - timedelta(days=8)
                #obj.update(**{'last_email_date': last_process})

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


@blueprint.route('/test/process', methods=['GET', 'DELETE'])
def api_process_test_user_subscription():
    """ Testing user subscriptions, it only process admin subscriptions """
    tiers = []

    user_list = User.objects(subscription__status="active", is_admin=True, my_email_summary=True)
    for user in user_list:
        tiers.append(api_subscription_process_user(user, test=True))

    if current_user.is_authenticated and current_user.is_admin:
        return get_response_formatted({'tiers': tiers})

    return get_response_formatted({"fruit": "banana"})


@blueprint.route('/process', methods=['GET', 'DELETE'])
def api_process_user_subscription():

    tier_2 = []

    check_subscription_status()

    # Tier 2 Process
    last_process = datetime.now() - timedelta(days=7)

    user_list = User.objects(current_subscription="tier2_monthly",
                             subscription__status="active",
                             __raw__=get_raw_query(last_process))
    for user in user_list:
        tier_2.append(api_subscription_process_user(user))

    # Tier 3 Process
    tier_3 = []
    last_process = datetime.now() - timedelta(hours=12)
    user_list = User.objects(current_subscription="tier3_monthly",
                             subscription__status="active",
                             __raw__=get_raw_query(last_process))

    for user in user_list:
        tier_3.append(api_subscription_process_user(user))

    if current_user.is_authenticated and current_user.is_admin:
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

    db_prompt.update(**update, is_admin=True)

    if db_user:
        subject = generate_email_subject(update)
        email = generate_links_email(update, update['ai_summary'])
        send_subscription_user_email(db_user, str(json['id']), subject, email)

    ret = {}
    return get_response_formatted(ret)


@blueprint.route('/redirect/<string:id>', methods=['GET', 'POST'])
def api_subscription_redirect_link(id):
    return redirect("/pages/prompt?id=" + id)


def api_subscription_dispatch_alert(user, article, tickers):
    """
        Send to telegram / discord / whatsapp / email... whatever the user has selected
    """
    from api.telegram.routes import api_telegram_create_message

    if user.my_telegram_chat_id:
        print(" DISPATCH TELEGRAM " + str(user.my_telegram_chat_id))

        msg = article.get_summary() + "\n"
        if article.ai_summary:
            msg += article.ai_summary

        api_telegram_create_message(user, title=article.get_no_bullshit(), message=msg)


def api_subscription_alert(db_news):
    from api.query_helper import mongo_to_dict_helper
    from api.ticker.models import DB_TickerUserWatchlist
    from api.ticker.routes import get_watchlist_or_create

    user_list = User.objects(subscription__status="active", my_instant_alerts=True)
    if not user_list:
        return {'error', 'NO USERS FOUND'}

    for article in db_news:
        print_g(f" CREATE NEWS ALERT FOR { article.source_title }")
        print(mongo_to_dict_helper(article.related_exchange_tickers))

        for user in user_list:
            print_b(f"-------- PROCESS USER { user.username } ------------")

            #watchlist = DB_TickerUserWatchlist.objects(username=user.username)
            #for w in watchlist:
            #    print(mongo_to_dict_helper(w))

            watchlist = DB_TickerUserWatchlist.objects(username=user.username,
                                                       exchange_tickers__in=article.related_exchange_tickers).limit(1)

            if not watchlist:
                print_r(" Article Not found in watchlist ")
                continue

            tickers = list(set(watchlist.first().exchange_tickers) & set(article.related_exchange_tickers))
            print_g(" Found articles in watchlist " + str(tickers))

            api_subscription_dispatch_alert(user, article, tickers)

    return db_news


@blueprint.route('/test/article/<string:news_query>', methods=['GET', 'POST'])
def api_subscription_test(news_query):
    """ /api/subscription/test_article/67680d5bf01e7761a3cef33b """
    if is_mongo_id(news_query):
        db_news = DB_News.objects(id=news_query)
    else:
        db_news = DB_News.objects(related_exchange_tickers__iendswith=":" +
                                  news_query).order_by('-creation_date').limit(1)

    if not db_news.first():
        return get_response_error_formatted(404, "ARTICLE NOT FOUND")

    ret = {'news': [api_subscription_alert(db_news)]}

    return get_response_formatted(ret)


@blueprint.route('/test/article', methods=['GET', 'POST'])
def api_subscription_test_latest_article_redirect_link():
    db_news = DB_News.objects(ai_summary__exists=1,
                              related_exchange_tickers__size=1).order_by('-creation_date').limit(1).first()
    if not db_news:
        return get_response_error_formatted(404, "ARTICLE NOT FOUND")

    return redirect("/api/subscription/test/article/" + str(db_news.id))


@blueprint.route('/referral/<string:referral_id>', methods=['GET', 'POST'])
def api_referral(referral_id):
    return redirect("/register?ref=" + referral_id)

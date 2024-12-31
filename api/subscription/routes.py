from datetime import datetime, timedelta

from api import get_response_formatted
from api.print_helper import *
from api.query_helper import *
from api.subscription import blueprint
from api.user.models import User
from flask_login import AnonymousUserMixin, current_user
from mongoengine import *
from mongoengine.errors import ValidationError


def api_subscription_process_user(db_user):
    print_b(" Process user " + db_user.username)

    last_process = datetime.now()
    db_user.update(**{'last_email_date': last_process})

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
        "$or": [
            {
                "last_email_date": {
                    "$lt": last_process
                }
            },
            {
                "last_email_date": {
                    "$exists": False
                }
            },
            {
                "last_email_date": None
            }
        ]
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


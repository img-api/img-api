from datetime import datetime, timedelta

from api import get_response_formatted
from api.print_helper import *
from api.query_helper import *
from api.subscription import blueprint
from api.user.models import User
from mongoengine import *
from mongoengine.errors import ValidationError


def api_subscription_process_user(db_user):
    print_b(" Process user " + db_user.username)

    #db_user.update(**{'last_email_date': datetime.now()})

    return db_user


def check_subscription_status():
    try:
        results = User.objects()
        for obj in results:
            if not obj.subscription:
                continue

            print_b(obj.username + " " + obj.subscription.status + " " + obj.current_subscription)
    except ValidationError as e:
        print(f"Offending object found: {obj.id}, Error: {e}")
        return obj.id  # Return the offending object's ID
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


@blueprint.route('/process', methods=['GET', 'DELETE'])
def api_process_user_subscription():
    tier_2 = []

    check_subscription_status()

    # Tier 2 Process
    last_process = datetime.today() - timedelta(days=7)
    user_list = User.objects(current_subscription="tier3_monthly",
                             subscription__status="active",
                             last_email_date__lte=last_process)
    for user in user_list:
        tier_2.append(api_subscription_process_user(user))

    # Tier 3 Process
    tier_3 = []
    last_process = datetime.today() - timedelta(days=1)
    user_list = User.objects(current_subscription="tier2_monthly",
                             subscription__status="active",
                             last_email_date__lte=last_process)

    for user in user_list:
        tier_3.append(api_subscription_process_user(user))

    return get_response_formatted({'tier2': tier_2, 'tier3': tier_3})

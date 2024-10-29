import stripe
import validators
from api import get_response_error_formatted, get_response_formatted
from api.config import get_host_name
from api.payment import blueprint
from api.print_helper import *
from flask import abort, current_app, jsonify, request, send_file
from flask_login import current_user


@blueprint.route('/config', methods=['GET'])
def get_config():
    # Retrieves two prices with the lookup_keys
    # `sample_basic` and `sample_premium`.  To
    # create these prices, you can use the Stripe
    # CLI fixtures command with the supplied
    # `seed.json` fixture file like so:
    #
    #    stripe fixtures seed.json
    #

    stripe_settings = current_app.config.get('STRIPE_SETTINGS', None)
    if not stripe_settings:
        return get_response_error_formatted(403, {'error_msg': "Please configure payment settings."})

    stripe.api_key = stripe_settings['api_key']
    prices = stripe.Price.list(lookup_keys=['tier1_monthly', 'tier2_monthly'])

    return jsonify(
        publishableKey=stripe_settings.get('publishable_key', None),
        prices=prices.data,
    )


@blueprint.route('/create_checkout_embedded', methods=['POST', 'GET'])
def create_checkout_session():

    stripe.api_version = '2022-08-01'
    stripe_settings = current_app.config.get('STRIPE_SETTINGS', None)
    if not stripe_settings:
        return get_response_error_formatted(403, {'error_msg': "Please configure payment settings."})

    PUBLIC_HOST = get_host_name()
    PRICE_ID = stripe_settings['prices']['tier1']['product_id']
    YOUR_DOMAIN = "https://" + PUBLIC_HOST

    stripe.api_key = stripe_settings['api_key']
    try:
        checkout_session = stripe.checkout.Session.create(
            ui_mode='embedded',
            line_items=[
                {
                    # Provide the exact Price ID (for example, pr_1234) of the product you want to sell
                    'price': PRICE_ID,
                    'quantity': 1,
                },
            ],
            mode='payment',
            return_url=YOUR_DOMAIN + '/return.html?session_id={CHECKOUT_SESSION_ID}',
        )
    except Exception as e:
        print_exception(e, "CRASHED CONNECTING TO STRIPE")

    ret = {'client_secret': checkout_session.client_secret}
    return get_response_formatted(ret)


@blueprint.route('/create_checkout_session', methods=['POST', 'GET'])
def create_checkout_redirect():

    stripe_settings = current_app.config.get('STRIPE_SETTINGS', None)
    if not stripe_settings:
        return get_response_error_formatted(403, {'error_msg': "Please configure payment settings."})

    stripe.api_key = stripe_settings['api_key']

    PUBLIC_HOST = get_host_name()

    tier = request.args.get("tier", 'tier1_monthly')
    prices = stripe.Price.list(lookup_keys=[tier])

    YOUR_DOMAIN = "https://" + PUBLIC_HOST

    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    # Provide the exact Price ID (for example, pr_1234) of the product you want to sell
                    'price': prices.data[0]['id'],
                    'quantity': 1,
                },
            ],
            mode='subscription',
            success_url=PUBLIC_HOST + '/api/payment/success?session_id={CHECKOUT_SESSION_ID}&alias_id=${aliasId}',
            cancel_url=PUBLIC_HOST + '/api/payment/cancel?session_id={CHECKOUT_SESSION_ID}',
        )
    except Exception as e:
        print_exception(e, "CRASHED CONNECTING TO STRIPE")

    ret = {'url': checkout_session.url}
    return get_response_formatted(ret)

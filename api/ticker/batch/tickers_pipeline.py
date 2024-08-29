import os
import re

import requests
import requests_cache

import pandas as pd
import yfinance as yf

from datetime import timedelta

from api.print_helper import *
from api.query_helper import *

from api.company.models import DB_Company
from api.ticker.models import DB_Ticker

# Perform complex queries to mongo
from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q

from api.ticker.connector_yfinance import fetch_tickers_info
from api.query_helper import copy_replace_schema
from api.ticker.tickers_helpers import standardize_ticker_format_to_yfinance


def ticker_pipeline_process(db_ticker, dry_run=False):
    """
        Our fetching pipeline will call different status

    """

    print_b("PROCESSING: " + db_ticker.exchg_tick())

    yticker = standardize_ticker_format_to_yfinance(db_ticker.exchg_tick())

    db_ticker.set_state("YFINANCE", dry_run)

    yf_obj = fetch_tickers_info(yticker)

    if not yf_obj:
        db_ticker.set_state("FAILED YFINANCE", dry_run)
        return

    db_company = db_ticker.get_company()

    info = yf_obj.info

    new_schema = {
        'website': 'website',

        'long_name': 'longName',
        'long_business_summary': 'longBusinessSummary',

        'main_address': 'address1',
        'main_address_1': 'address2',
        'city': 'city',
        'state': 'state',
        'zipcode': 'zip',
        'country': 'country',
        'phone_number': 'phone',

        'gics_sector': 'sector',
        'gics_sub_industry': 'industry',
    }

    myupdate = prepare_update_with_schema(info, new_schema)

    if 'companyOfficers' in info:
        company_officers = info['companyOfficers']
        for officer in company_officers:
            print_b(f"TODO: Create person {officer['name']} => {officer['title']}")


    if not dry_run:
        db_company.update(**myupdate, validate=False)
        db_ticker.set_state("PROCESSED", dry_run)

    return db_ticker
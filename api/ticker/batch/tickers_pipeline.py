import os
import re
from datetime import timedelta

import pandas as pd
import requests
import requests_cache
from api.company.models import DB_Company
from api.print_helper import *
from api.query_helper import *
from api.ticker.models import DB_Ticker
# Perform complex queries to mongo
from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q

import yfinance as yf


def ticker_pipeline_process(db_ticker, dry_run=False):
    """
        Our fetching pipeline will call different status
    """
    print_b("PROCESSING TICKER " + str(db_ticker.exchange) + ":" + str(db_ticker.ticker))
    if not dry_run:
        db_ticker.set_state("PROCESSED")

    return db_ticker

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
from .tickers_pipeline import ticker_pipeline_process

# RAW basic implementation before going for a future implmentation using
# Something like temporal.io

# https://learn.temporal.io/getting_started/python/first_program_in_python/

def ticker_process_batch(end=None, dry_run=False, BATCH_SIZE=5):
    """
    Gets a list of tickers and calls the different APIs to capture and process the data.

    Limit to BATCH_SIZE so we don't ask for too many at once to all APIs
    """

    # Get tickers processed more than X days ago.
    # Less than or Equal to Last processed

    if not end:
        end = get_timestamp_verbose("10 days")

    query = Q(last_processed_date__lte=end) | Q(last_processed_date__lte=None)
    tickers = DB_Ticker.objects(query)[:BATCH_SIZE]

    for db_ticker in tickers:
        db_ticker.set_state("PIPELINE_START", dry_run)

        try:
            ticker_pipeline_process(db_ticker, dry_run=dry_run)
        except Exception as e:
            print_exception(e, "CRASHED PROCESSING BATCH")

    return tickers

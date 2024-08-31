import os
import re

import requests
import requests_cache

import pandas as pd
import yfinance as yf

from datetime import timedelta

from api.print_helper import *
from api.company.models import DB_Company
from api.news.models import DB_News

# Perform complex queries to mongo
from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q


def yfetch_process_news(item):
    """
    Downloads the news into disk
    """
    print(" Hello world ")
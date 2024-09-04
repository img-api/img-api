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

from api.ticker.batch.html.html_helper import get_html, save_html_to_file


def yfetch_process_news(item, web_driver = None):
    """
    Downloads the news into disk
    """
    from api.ticker.batch.html.selenium_integration import get_webdriver

    print_b("NEWS -> " + item.link)

    data_folder = item.get_data_folder()
    print_b("DATA FOLDER: " + data_folder)

    soup, raw_html = get_html(item.link)

    filename = str(item.id) + ".html"
    save_html_to_file(raw_html, filename, data_folder)

    if web_driver:
        print_b(" REUSING WEBDRIVER ")
        driver = web_driver
    else:
        driver = get_webdriver()

    driver.get(raw_html)

    if not web_driver:
        driver.quit()

    # Reindex because we haven't finish this code
    item.set_state("WAITING_INDEX")

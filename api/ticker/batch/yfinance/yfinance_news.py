import os
import random
import re
import time
from datetime import timedelta

import pandas as pd
import requests
import requests_cache
from api.company.models import DB_Company
from api.news.models import DB_News
from api.print_helper import *
from api.ticker.batch.html.html_helper import get_html, save_html_to_file
# Perform complex queries to mongo
from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options

import yfinance as yf


def clean_article(article):
    """Cleans \n character from article"""

    article = re.sub("\n", " ", article)
    return article

def yfetch_process_news(item, web_driver=None):
    """
    Downloads the news into disk
    """
    from api.ticker.batch.html.selenium_integration import get_webdriver

    print_b("NEWS -> " + item.link)

    data_folder = item.get_data_folder()
    print_b("DATA FOLDER: " + data_folder)

    if web_driver:
        print_b(" REUSING WEBDRIVER ")
        driver = web_driver
    else:
        driver = get_webdriver()

    articles = []

    print_b(" PUBLISHER " + item['publisher'])
    if item["publisher"] not in ["Barrons", "MT Newswires", "Investor's Business Daily", "Yahoo Finance Video"]:
        #user_agent = random.choice(firefox_user_agents)
        #options = Options()
        #options.set_preference("general.useragent.override", user_agent)

        driver.get(item["link"])

        try:
            # We get the consent
            link = driver.find_element(By.CLASS_NAME, "accept-all")
            link.click()
        except Exception as e:
            pass

        try:
            link = driver.find_element(By.CLASS_NAME, "readmoreButtonText")
            link.click()
        except Exception as e:
            print_exception(e, "CRASHED")
            pass

        try:
            article = driver.find_element(By.CLASS_NAME, "caas-body")
            article = clean_article(article.text)
        except:
            print(item["publisher"])
            article = ""
            paragraphs = driver.find_elements(By.TAG_NAME, "p")
            for paragraph in paragraphs:
                article += paragraph.text
            article = clean_article(article)
        finally:
            articles.append(article)

    else:
        if item["publisher"] in ["Barrons", "MT Newswires"]:
            if "title" in item:
                articles.append(item["title"])

        elif item["publisher"] == "Investor's Business Daily":
            while True:
                try:
                    article = get_IBD_articles(item["link"])
                    if article != "":
                        break
                except:
                    time.sleep(random.randint(5, 15))

            article = clean_article(article)
            articles.append(article)

    #soup, raw_html = get_html(item.link)

    #filename = str(item.id) + ".html"
    #save_html_to_file(raw_html, filename, data_folder)


    if not web_driver:
        driver.quit()

    # Reindex because we haven't finish this code

    if len(articles) > 0:
        item.articles = articles
        item.save(validate=False)
        item.set_state("INDEXED")
    else:
        item.set_state("ERROR: ARTICLES NOT FOUND")

def news_fetcher():
    return
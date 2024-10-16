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


firefox_user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:103.0) Gecko/20100101 Firefox/103.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:102.0) Gecko/20100101 Firefox/102.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:101.0) Gecko/20100101 Firefox/101.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:100.0) Gecko/20100101 Firefox/100.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:103.0) Gecko/20100101 Firefox/103.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0",
    "Mozilla/5.0 (Linux x86_64; rv:103.0) Gecko/20100101 Firefox/103.0",
    "Mozilla/5.0 (Linux x86_64; rv:102.0) Gecko/20100101 Firefox/102.0"
]


def clean_article(article):
    """Cleans \n character from article"""

    article = re.sub("\n", " ", article)
    return article

def get_webdriver():
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.chrome.options import Options

    chrome_executable_path = "./chrome/chrome/linux-128.0.6613.86/chrome-linux64/chrome"
    chromedriver_path = "./chrome/chromedriver-linux64/chromedriver"

    # Step 1: Setup Chrome options
    chrome_options = Options()
    chrome_options.binary_location = chrome_executable_path  # Specify the location of the Chrome binary

    chrome_options.add_argument("--headless")  # Optional, run Chrome in headless mode
    chrome_options.add_argument("--disable-gpu")  # Optional, disable GPU acceleration
    chrome_options.add_argument("--window-size=1920,1200")  # Optional, set window size

    # Step 2: Initialize the Chrome WebDriver

    # We have the driver in our system
    driver = webdriver.Chrome(service=ChromeService(chromedriver_path), options=chrome_options)

    return driver

def get_IBD_articles(url):
    "Use this for scraping news from investors.com"

    article = ""
    user_agent = random.choice(firefox_user_agents)
    options.set_preference("general.useragent.override", user_agent)
    driver = webdriver.Firefox(options=options)
    time.sleep(2)
    link = driver.find_element(By.LINK_TEXT, "Continue Reading")
    link.click()
    time.sleep(3)
    paragraphs = driver.find_elements(By.TAG_NAME, "p")
    for paragraph in paragraphs:
        if paragraph.text != "":
            article += paragraph.text
        if "YOU MIGHT ALSO LIKE" in paragraph.text:
            break
    article.replace("YOU MIGHT ALSO LIKE", "")
    driver.quit()
    return article


def yfetch_process_news(item, web_driver=None):
    """
    Downloads the news into disk
    """

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

        if not item['link'] or 'localhost' in item['link']:
            return

        print_b(" LOADING " + item['link'])
        driver.get(item["link"])

        try:
            time.sleep(random.randint(2, 5))
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

        driver.close()
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

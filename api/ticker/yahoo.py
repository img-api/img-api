import os
import re


import requests
import requests_cache

import urllib
from urllib.request import urlopen, Request
import pandas as pd
import yfinance as yf

import time
import selenium
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options

import datetime
from datetime import timedelta

from api.print_helper import *
from api.company.models import DB_Company

from .models import DB_Ticker

firefox_user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:103.0) Gecko/20100101 Firefox/103.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:102.0) Gecko/20100101 Firefox/102.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:101.0) Gecko/20100101 Firefox/101.0",
        "Mozilla/5/.0 (Windows NT 10.0; Win64; x64; rv:100.0) Gecko/20100101 Firefox/100.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:103.0) Gecko/20100101 Firefox/103.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:102.0) Gecko/20100101 Firefox/102.0",
        "Mozilla/5.0 (Linux x86_64; rv:103.0) Gecko/20100101 Firefox/103.0",
        "Mozilla/5.0 (Linux x86_64; rv:102.0) Gecko/20100101 Firefox/102.0"
    ]

class Yahoo:
    def get_yahoo_publishers(self):

        """Gets list of publishers connected to Yahoo Finance"""

        yahoo_publishers = set()
        tickers = ["AMGN", "KO", "MSFT", "NVDA", "WM"]
        for ticker in tickers:
            ticker = yf.Ticker(ticker)
            for item in ticker.news:
                yahoo_publishers.add(item["publisher"])
        return yahoo_publishers
    

    def date_from_unix(self, string):

        """Takes unix format and converts it into datetime object"""

        return datetime.datetime.fromtimestamp(float(string))

    #completed
    def clean_article(self, article):

        """Takes in article string as input, removes all instances of \n from it"""

        article = re.sub("\n", " ", article)
        article = article.replace("Sign in to access your portfolio", "")
        return article


    def save_article(self, date, link, title, news_type, publisher, article, uuid, related_tickers = None):

        """Creates a MongoDB article object. 
        Saves article into the relevant database"""

        news = DB_News(
            creation_date = date,
            last_visited_date = datetime.datetime.now(),
            link = link,
            title = title,
            news_type = news_type,
            publisher = publisher,
            news_article = article,
            external_uuid = uuid,
            related_exchange_tickers = related_tickers
        )
        news.save()


        
    def download_yahoo_news(self, ticker):
        ticker = yf.Ticker(f"{ticker}")
        for item in ticker.news:
            if item["publisher"] not in ["Barrons", "MT Newswires", "Investor's Business Daily", "Yahoo Finance Video"]:
                success, article = self.download_article(item["link"])
                article = clean_article(article)
                print(item["publisher"], article)
                if success == 0:
                    news_type = "denied"
                elif success == 1:
                    news_type = "html"
                else:
                    news_type = "text"
                self.save_article(
                            date = self.date_from_unix(item["providerPublishTime"]),
                            link = item["link"],
                            title = item["title"],
                            news_type = news_type,
                            publisher = item["publisher"],
                            article = article,
                            uuid = "Y_" + item["uuid"],
                        related_tickers = item["relatedTickers"])
            else:
                if item["publisher"] == "Investor's Business Daily":
                    success, html = self.download_ibd(item["link"])
                    if success == 1:
                        news_type = "html"
                    self.save_article(
                            date = self.date_from_unix(item["providerPublishTime"]),
                            link = item["link"],
                            title = item["title"],
                            news_type = news_type,
                            publisher = item["publisher"],
                            article = article,
                            uuid = "Y_" + item["uuid"],
                        related_tickers = item["relatedTickers"])
        

    def download_article(self, url):
        user_agent = random.choice(firefox_user_agents)
        options = Options()
        options.set_preference("general.useragent.override", user_agent)
        driver = webdriver.Firefox(options=options)
        try:
            driver.get(url)
        
        except:
            #save into denied
            return [0, ""]
        
        try:
            # Wait until the button is visible
            readmore_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CLASS_NAME, "readmore-button"))
            )

            # Optionally, scroll to the button if necessary
            actions = ActionChains(driver)
            actions.move_to_element(readmore_button).perform()

            # Click the button
            readmore_button.click()
        
            print("Clicked on the 'Read More' button successfully.")

        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(random.randint(2,10)) 
        
        try:
            html = driver.page_source
        except Exception as e:
            print(f"Error: {e}")
            driver.quit()
            return [0, ""]
        try:
            article = driver.find_element(By.TAG_NAME, "article")
            article = self.clean_article(article.text)
            driver.quit()
            return [2, article]
        except Exception as e:
            print(f"Error: {e}, {url}")
            driver.quit()
            return [1, html]



                
    def download_ibd(self, url):
        user_agent = random.choice(firefox_user_agents)
        options = Options()
        options.set_preference("general.useragent.override", user_agent)
        driver = webdriver.Firefox(options=options)

        driver.get(url)
        time.sleep(random.randint(4,7))
        try:
            link = driver.find_element(By.LINK_TEXT, "Continue Reading")
            link.click()
        except:
            pass
        
        time.sleep(5)
        html = driver.page_source
        driver.quit()
        return html

yahoo = Yahoo()
yahoo.download_yahoo_news("msft")
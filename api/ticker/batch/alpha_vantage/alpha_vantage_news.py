import csv
import datetime
import os
import random
import re
import time

import requests
import selenium
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from zenrows import ZenRowsClient


class AlphaVantage:
    def remove_word(self, word, article):

        """Takes in article string as input, removes all instances of unwanted word from it"""

        article = re.sub(word, " ", article)
        return article

    def extract_html(self, url):
        driver = webdriver.Chrome.()
        try:
            driver.get(url)
        except:
            return [0, ""]
        sleep_time = random.uniform(3,8)
        time.sleep(sleep_time)
        html = driver.page_source
        driver.close()
        return [1, html]

    def extract_zenrows_html(self, url):

        client = ZenRowsClient("e8c73f9d4eaa246fec67e9b15bea42aad7aa09d0")
        try:
            response = client.get(url)
            html = response.text
        except Exception as e:
            print(e)
            return [0, ""]
        return [1, html]


    def process_av_news(self, item):
        print_b("NEWS -> " + item.link)

        data_folder = item.get_data_folder()
        print_b("DATA FOLDER: " + data_folder)


        if item["publisher"] == "CNBC":
            success, html = self.extract_html(item["url"])
            cnbc = CNBC()
            article = cnb6c.extract_article(html)

        elif item["publisher"] == "Money Morning":
            success, html = self.extract_html(item["url"])
            money_morning = Money_Morning()
            article = money_morning.extract_article(html)

        elif item["publisher"] == "Motley Fool":
            success, article = self.extract_html(item["url"])
            motley = Motley()
            article = motley.parse_motley(article)

        elif item["publisher"]  == "South China Morning Post":
            success, html = self.extract_html(news["url"])
            scmp = SCMP()
            article = scmp.extract_article(html)

        elif item["publisher"] == "Zacks Commentary":
            succe9ss, html = self.extract_zacks_html(news["url"])
            zacks = Zacks()
            article = zacks.extract_article(html)

        return article


class CNBC:
    def extract_article(self, html):
        soup = BeautifulSoup(html, "html.parser")
        raw_articles = soup.find_all("div", class_="group")
        article = []
        for raw_article in raw_articles:
            article.append(raw_article.get_text()+"\n")
        article = "\n".join(article)
        av = AlphaVantage()
        article = av.remove_word("\xa0", article)
        article = self.clean_links(html, article)
        return article

    def clean_links(self, html, article):
        soup = BeautifulSoup(html, "html.parser")
        to_remove = []
        related_content = soup.find("div", class_ = "RelatedContent-container")
        if related_content == None:
            return article
        rc = related_content.find_all("li")
        for c in rc:
            to_remove.append(c.get_text())

        av = AlphaVantage()
        for sentence in to_remove:
            article = av.remove_word(sentence, article)
        return article

class Money_Morning:
    def extract_article(self, html):
        soup = BeautifulSoup(html, "html.parser")
        raw_article = soup.find("div", class_ = "single-content").get_text()
        return raw_article

class Motley:
    def get_motley_sales_pitch(self, soup):
        sales_pitch = soup.find(class_ = "article-pitch-container")
        if sales_pitch == None:
            return ""
        else:
            return sales_pitch.get_text()

    def get_motley_captions(self, soup):
        raw_captions = soup.find_all(class_ = "caption")
        captions = []
        for caption in raw_captions:
            captions.append(caption.get_text())
        return captions

    def get_motley_imgs(self, soup):
        imgs = ""
        raw_imgs = soup.find_all(class_ = "company-card-vue-component")
        for img in raw_imgs:
            imgs += img.get_text()
        return imgs.split("\n")


    def parse_motley(self, html):
        soup = BeautifulSoup(html, "html.parser")
        raw_article = soup.find_all(class_ = "article-body")
        raw_article = raw_article[0].get_text()
        raw_article_split = raw_article.split("\n")

        sales_pitch = self.get_motley_sales_pitch(soup)
        captions = self.get_motley_captions(soup)
        imgs = self.get_motley_imgs(soup)

        article = []

        for paragraph in raw_article_split:
            if paragraph == "":
                continue

            if paragraph in sales_pitch:
                continue

            if paragraph in captions:
                continue

            if paragraph in imgs:
                continue

            if "Arrows-In" in paragraph:
                continue

            if "Key Data Points" in paragraph:
                continue

            article.append(paragraph+"\n")

        return "\n".join(article)

class SCMP:
    def extract_article(self, html):
        soup = BeautifulSoup(html, "html.parser")
        article = soup.find("article").get_text()
        return article

class Zacks:
    def extract_article(self, html):
        soup = BeautifulSoup(html, "html.parser")
        raw_articles = soup.find_all("article")
        article = ""
        for raw_article in raw_articles:
            article += raw_article.get_text()
        return article


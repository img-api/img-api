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

class FinvizNews:
    def get_yahoo_publishers(self):

        """Gets list of publishers connected to Yahoo Finance"""

        yahoo_publishers = set()
        tickers = ["AMGN", "KO", "MSFT", "NVDA", "WM"]
        for ticker in tickers:
            ticker = yf.Ticker(ticker)
            for item in ticker.news:
                yahoo_publishers.add(item["publisher"])
        return yahoo_publishers
    
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

    #completed
    def parse_finviz_dates(self, date_data):
        if len(date_data) == 1:
            time = date_data[0]
        else:
            time = date_data[1]
        today = datetime.today()
        date = today.date()
        parsed_date = str(date) + " " + str(time)
        parsed_date = datetime.datetime.strptime(parsed_date, "%Y-%m-%d %I:%M%p")
        formatted_date = parsed_date.strftime("%Y-%m-%d %H:%M:%S")
        return formatted_date
    
    def extract_domain_name(self, url):

        """Extracts domain name from a URL"""        

        parsed_url = urlparse(url)
        base_url = parsed_url.netloc
        base_url = re.sub("www.", "", base_url)
        base_url = re.sub(".com", "", base_url)
        return base_url
    
    def extract_youtube(self, video_url):
        yt = YouTube(video_url)
        audio_stream = yt.streams.filter(only_audio=True).first()
        audio_buffer = io.BytesIO(audio_stream.stream_to_buffer().getbuffer())
        model = whisper.load_model("base")
        transcription = model.transcribe(audio_buffer)
        audio_buffer = None
        return transcription["text"]
    
    def download_nasdaq(self, url):

        """Takes in NASDAQ url as input, retrieves news articles from Nasdaq and returns string"""


        user_agent = random.choice(firefox_user_agents)
        options = Options()
        options.set_preference("general.useragent.override", user_agent)
        driver = webdriver.Firefox(options=options)
        try:
            driver.get(url)
        except:
            return [0, ""]
        time.sleep(random.randint(1,5))
        article = driver.find_element(By.CLASS_NAME, "body__content")

        if article == "":
            return [1, driver.page_source]

        article = self.clean_article(article.text)
        return [2, article]


    #under construction. pls do very heavy debugging & submit a working prototype
    def extract_article(self, url):

        """Takes in url as input, retrieves article via p tag and returns article as string-"""

        user_agent = random.choice(firefox_user_agents)
        options = Options()
        options.set_preference("general.useragent.override", user_agent)
        driver = webdriver.Firefox(options=options)
        try:
            driver.get(url)
        except:
            return [0, ""]

        #rate limiting
        time.sleep(random.randint(4, 10))

        
        try:
            html = driver.page_source
        except:
            return [0, ""]

        try:
            article = driver.find_element(By.TAG_NAME, "article")
        except:
            print(url, "Element not found")
            return [1, html]
        
        article = self.clean_article(article.text)
        return [2, article]

    
    def download_finviz_news(self, ticker):

        """Downloads news from finviz.com"""
        
        yahoo_publishers = self.get_yahoo_publishers()
        url = "https://finviz.com/quote.ashx?t="+ticker+"&p=d"
        articles = []
        links = set()

        req = Request(url=url, headers={"user-agent": "my-app"})
        response = urlopen(req)

        html = BeautifulSoup(response, "html.parser")

        #continue scraping
        news_articles = html.find_all("tr", class_ = "cursor-pointer has-label")
        date = datetime.datetime.today()

        for n in news_articles:
            link = n.div.div.a["href"]
            base_url = self.extract_domain_name(link)
            if base_url in yahoo_publishers:
                continue

            if "yahoo" in base_url:
                continue

            if "insidermonkey" in base_url:
                continue

            date_data = n.td.text.strip().split(" ")
            date_data = self.parse_finviz_dates(date_data)
            

            print("Currently scraping", base_url)
            title = n.div.div.a.text

            if "youtube" in base_url:
                #still under construction
                continue
                #success, article = self.extract_video(link)
            else:
                if "nasdaq" in base_url.lower():
                    success, article = self.download_nasdaq(link)

                else:

                    success, article = self.extract_news(link)
                uuid = f"F_{ticker}_" + str(datetime.datetime.now())
                if success == 0:
                    news_type = "denied"
                elif success == 1:
                    news_type = "html"
                else:
                    news_type = "text"
                self.save_article(
                    date = date_data,
                    link = link,
                    title = title,
                    news_type = news_type,
                    publisher = base_url,
                    article = article,
                    uuid = uuid,
                related_tickers = None)
0

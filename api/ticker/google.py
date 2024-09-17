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

class GoogleNews:
    def get_yahoo_publishers(self):

        """Gets list of publishers connected to Yahoo Finance"""

        yahoo_publishers = set()
        tickers = ["AMGN", "KO", "MSFT", "NVDA", "WM"]
        for ticker in tickers:
            ticker = yf.Ticker(ticker)
            for item in ticker.news:
                yahoo_publishers.add(item["publisher"])
        return yahoo_publishers
    
    #completed
    def get_google_publishers(self):

        """Gets list of publishers connected to Google News"""

        google_publishers = set()
        gn = GoogleNews()
        tickers = ["AMGN", "KO", "MSFT", "NVDA", "WM"]
        for ticker in tickers:
            search = gn.search(f"{ticker}")
            for result in search["entries"]:
                google_publishers.add(result["source"]["title"])
        return google_publishers

    def date_from_unix(self, string):

        """Takes unix format and converts it into datetime object"""

        return datetime.datetime.fromtimestamp(float(string))

    
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
    def parse_google_dates(self, date_str):
    
        """Parses dates from Google News"""

        parsed_date = datetime.datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z")
        # Format the date into the desired format
        formatted_date = parsed_date.strftime("%Y-%m-%d %H:%M:%S")
        return formatted_date
    
    print(date_from_unix("1726050403"))


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
    
    def download_google_news(self, ticker):

        """Takes in stock ticker as input, retrieves news articles from Google News and returns
        list of articles"""    

        articles = []

        gn = GoogleNews()
        search = gn.search(f"{ticker}")
        yahoo_publishers = self.get_yahoo_publishers()
        #loop through search results
        for result in search["entries"]:
            if result["source"]["title"] not in yahoo_publishers:

                #extract nasdaq
                if result["source"]["title"] == "Nasdaq":
                    success, article = self.download_nasdaq(result["link"])
                    if success == 0:
                        news_type = "denied"
                    elif success == 1:
                        news_type = "html"
                    else:
                        news_type = "text"
                    self.save_article(
                        date = self.parse_google_dates(result["published"]),
                        link = result["link"],
                        title = result["title"],
                        news_type = news_type,
                        publisher = result["source"]["title"],
                        article = article,
                        uuid = "G_" + result["id"],
                    related_tickers = None)


                else:
                    success, article = self.extract_news(result["link"])
                    if success == 0:
                        news_type = "denied"
                    elif success == 1:
                        news_type = "html"
                    else:
                        news_type = "text"
                    self.save_article(
                        date = self.parse_google_dates(result["published"]),
                        link = result["link"],
                        title = result["title"],
                        news_type = news_type,
                        publisher = result["source"]["title"],
                        article = article,
                        uuid = "G_" + result["id"],
                    related_tickers = None)
        return articles, links
    
    
    
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

        article = clean_article(article.text)
        return [2, article]


    #under construction. pls do very heavy debugging & submit a working prototype
    def extract_news(self, url):

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

        article = ""
        i = 0
        while i < 3:
            paragraphs = driver.find_elements(By.TAG_NAME, "p")
            for paragraph in paragraphs:
                article += paragraph.text
            if article != "":
                break
            i += 1

        driver.quit()
        if article == "":
            return [1, driver.page_source]
        else:
            article = self.clean_article(article)
            return [2, article]


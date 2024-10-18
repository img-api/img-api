import datetime
import requests
from alpha_vantage_news import *

def parse_av_dates(self, date_string):
    parsed_date = datetime.datetime.strptime(date_string, '%Y%m%dT%H%M%S')
    return parsed_date

def format_av_dates(self, date):
    date = re.sub("-", "", date)
    date = re.sub(" ", "", date)
    date = re.sub(":", "", date)
    return date



def get_av_news(ticker):
    news = []
    url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers=NVDA&apikey=JIHXVRY5SPIH16C9"
    r = requests.get(url)
    data = r.json()
    for news_item in data["feed"]:
        if news_item["source"] in ["CNBC", "Money Morning", "Motley Fool", "South China Morning Post", "Zacks Commentary":
            news.append(news_item)
    return news



def av_pipeline_process(db_ticker):

    #get the ticker name
    ticker = db_ticker.ticker
    news = get_av_news(ticker)
    for item in news:
        update = False
        db_news = DB_News.objects(external_uuid=item['uuid']).first()
        if db_news:
            # We don't update news that we already have in the system
            print_b(" ALREADY INDEXED " + item['link'])
            update = True
            #continue
    
        raw_data_id = 0
        try:
            # It should go to disk or something, this is madness to save it on the DB
    
            news_data = DB_DynamicNewsRawData(**item)
            news_data.save()
            raw_data_id = str(news_data['id'])
        except Exception as e:
            print_exception(e, "SAVE RAW DATA")
    
        #standardize between the different news sources
        #alpha vantage doesn't have related tickers*
        new_schema = {
                    "title": date,
                    "link": url,
                    "external_uuid": f"av_{ticker}_{format_av_date(date)}",
                    "publisher": news_item["source"]
                }
        
    
        #what does this line do?
        myupdate = prepare_update_with_schema(item, new_schema)
    
        extra = {
            'source': 'ALPHAVANTAGE',
            'status': 'WAITING_INDEX',
            'raw_data_id': raw_data_id
        }
    
        myupdate = {**myupdate, **extra}
    
        if not update:
            db_news = DB_News(**myupdate).save(validate=False)
        
        article = process_av_news(item)
    #where do you save article?
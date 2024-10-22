import datetime
import requests
import re
from alpha_vantage_news import *
from api.print_helper import *
from api.query_helper import *

def parse_av_dates(date_string):
    parsed_date = datetime.datetime.strptime(date_string, '%Y%m%dT%H%M%S')
    return parsed_date

def format_av_dates(date):
    date = re.sub("-", "", date)
    date = re.sub(" ", "", date)
    date = re.sub(":", "", date)
    return date

def generate_external_uuid(item, ticker):
    date = parse_av_date(item["time_published"])
    date = format_av_dates(date)
    return f"av_{ticker}_{date}"


def get_av_news(ticker):
    news = []
    url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers=NVDA&apikey=JIHXVRY5SPIH16C9"
    r = requests.get(url)
    data = r.json()
    for news_item in data["feed"]:
        if news_item["source"] in ["CNBC", "Money Morning", "Motley Fool", "South China Morning Post", "Zacks Commentary"]:
            news.append(news_item)
    return news



def av_pipeline_process(db_ticker):

    #get the ticker name
    ticker = db_ticker.ticker
    news = get_av_news(ticker)
    for item in news:
        update = False
        
        external_uuid = generate_external_uuid(item, ticker)
        db_news = DB_News.objects(external_uuid=external_uuid).first()
        if db_news:
            # We don't update news that we already have in the system
            print_b(" ALREADY INDEXED " + item[["url"]])
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
        date = parse_av_date(item["time_published"])
        new_schema = {
                    "date": date,
                    "title": item["title"],
                    "link": item["url"],
                    "external_uuid": external_uuid,
                    "publisher": item["source"]
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
        
        av = AlphaVantage()
        article = av.process_av_news(db_news)
        db_ticker.set_state("PROCESSED")

        #this line may be buggy
        if article != "":
            db_news.articles.append(article)
            item.save(validate=False)
            item.set_state("INDEXED")
        else:
            item.set_state("ERROR: ARTICLES NOT FOUND")
import copy
import re
import socket
from datetime import datetime

import requests
from api import (admin_login_required, api_key_or_login_required,
                 chroma_client, get_response_error_formatted,
                 get_response_formatted)
from api.company.models import DB_Company
from api.config import get_api_AI_service, get_api_entry, is_api_development
from api.file_cache import api_file_cache
from api.news import blueprint
from api.news.models import DB_News
from api.print_helper import *
from api.query_helper import (build_query_from_request, is_mongo_id,
                              validate_and_convert_dates)
from api.subscription.routes import api_subscription_alert
from flask import request
from flask_login import current_user

collection = chroma_client.get_or_create_collection("api_news")


def chromadb_delete_all():
    collection.delete(where={})


def convert_article(article):

    try:
        keywords = article['AI']['gif_keywords']
    except:
        keywords = ""

    document = str(article.source_title) + " " + str(article.ai_summary) + " " + str(keywords)

    et = ",".join(list(article.related_exchange_tickers))
    metadata = {
        'related_exchange_tickers': et,
    }

    return document, metadata


def chromadb_index_document(article):
    print_b(f"CHROMA INDEX {str(article.id)} ")

    doc_id = "news_" + str(article.id)

    results = collection.get(ids=[doc_id])

    document, metadata = convert_article(article)
    if results['ids']:
        # If the ID exists, update the document
        collection.update(ids=[doc_id], documents=[article], metadatas=[new_metadata])
        print(f"Document with ID '{doc_id}' updated.")
        return

    collection.add(ids=[doc_id], documents=[document], metadatas=[metadata])

    return {'id': doc_id, 'doc': document, 'meta': metadata}

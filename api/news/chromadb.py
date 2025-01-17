import copy
import re
import socket
from datetime import datetime

import requests
from api import (admin_login_required, api_key_or_login_required,
                 get_response_error_formatted, get_response_formatted)
from api.company.models import DB_Company
from api.config import get_api_AI_service, get_api_entry, is_api_development
from api.file_cache import api_file_cache
from api.news import blueprint
from api.news.models import DB_News
from api.print_helper import *
from api.query_helper import (build_query_from_request, date_to_unix,
                              is_mongo_id, validate_and_convert_dates)
from api.subscription.routes import api_subscription_alert
from flask import request
from flask_login import current_user

import chromadb
from chromadb.config import Settings

chroma_client = chromadb.HttpClient(
    host="localhost",
    port=8000,
    settings=Settings(allow_reset=True, anonymized_telemetry=False),
)
chroma_client.heartbeat()

# from chromadb.utils import embedding_functions

# default_ef = embedding_functions.DefaultEmbeddingFunction()

# val = default_ef(["foo"])
# print(val)

# sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
#    model_name="all-MiniLM-L6-v2"
# )

collection = chroma_client.get_or_create_collection("api_news")


def chromadb_delete_all():
    chroma_client.delete_collection("api_news")


def iso_date(epoch_seconds):
    return datetime.datetime.fromtimestamp(epoch_seconds).isoformat()


def convert_article(article):

    try:
        keywords = article["AI"]["gif_keywords"]
    except:
        keywords = ""

    document = (str(article.source_title) + " " + str(article.ai_summary) + " " + str(keywords))

    et = ",".join(list(article.related_exchange_tickers))
    metadata = {
        "related_exchange_tickers": et,
        "date": date_to_unix(article.creation_date),
    }

    return document, metadata


def chromadb_index_document(article):
    print_b(f"CHROMA INDEX {str(article.id)} ")

    doc_id = "news_" + str(article.id)

    # results = collection.get(ids=[doc_id])

    document, metadata = convert_article(article)

    # If the ID exists, update the document
    collection.upsert(ids=[doc_id], documents=[document], metadatas=[metadata])

    return {"id": doc_id, "doc": document, "meta": metadata}


def chromadb_search(query, limit=10):
    results = collection.query(query_texts=[query], n_results=limit)

    return results

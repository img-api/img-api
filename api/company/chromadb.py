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

collection = chroma_client.get_or_create_collection("api_company")
col_comp_info = chroma_client.get_or_create_collection("api_company_info")


def chromadb_delete_all_company():
    global collection, col_comp_info

    chroma_client.delete_collection("api_company")
    chroma_client.delete_collection("api_company_info")
    collection = chroma_client.get_or_create_collection("api_company")
    col_comp_info = chroma_client.get_or_create_collection("api_company_info")


def iso_date(epoch_seconds):
    return datetime.datetime.fromtimestamp(epoch_seconds).isoformat()


def convert_company(company, add_info=False):
    from api.ticker.tickers_helpers import \
        standardize_ticker_format_to_yfinance

    document = str(company.company_name) + " "

    if company.long_name and company.company_name != company.long_name:
        document += str(company.long_name) + " "

    ets = []
    for t in company.exchange_tickers:
        ets.append(standardize_ticker_format_to_yfinance(t))

    document += " ".join(list(set(ets))) + " "

    if add_info:
        document += str(company.long_business_summary)
        document += str(company.ai_summary)

        metadata = {
            "tickers": " ".join(list(company.exchange_tickers)),
        }
    else:
        print_g(document)
        metadata = {}

    return document.strip(), metadata


def chromadb_company_index_document(company):
    doc_id = str(company.id)
    document, metadata = convert_company(company, False)

    # If the ID exists, update the document
    collection.upsert(ids=[doc_id], documents=[document])

    document, metadata = convert_company(company, True)
    col_comp_info.upsert(ids=[doc_id], documents=[document], metadatas=[metadata])

    return {"id": doc_id, "doc": document, "meta": metadata}


def chromadb_company_search(query, limit=10):
    results = collection.query(query_texts=[query], n_results=limit)

    return results

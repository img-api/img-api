import binascii
import io
import random
import re
import time

import bcrypt
import qrcode
import requests
import validators
from api import (api_key_login_or_anonymous, api_key_or_login_required, cache,
                 get_response_error_formatted, get_response_formatted)
from api.news import blueprint
from api.news.models import DB_News
from api.print_helper import *
from api.query_helper import build_query_from_request, mongo_to_dict_helper
from api.tools.validators import get_validated_email
from flask import (Response, abort, current_app, jsonify, redirect, request,
                   send_file)
from flask_login import current_user
from mongoengine.queryset import QuerySet
from mongoengine.queryset.visitor import Q

# Predefined lists of good and bad sentiment words
GOOD_SENTIMENTS = ['bullish', 'optimistic', 'positive', 'buy', 'growth']
BAD_SENTIMENTS = ['bearish', 'pessimistic', 'negative', 'sell', 'decline']

SENTIMENT_SCORES = {
    # Highly positive words
    "bullish": 10, "optimistic": 10, "thriving": 9, "booming": 9,
    "positive": 8, "growth": 8, "expanding": 8, "buy": 7, "prosperous": 7,

    # Moderately positive words
    "hopeful": 6, "encouraging": 6, "rising": 5, "improving": 5, "stable": 4,

    # Neutral or slightly positive words
    "neutral": 0, "steady": 3, "balanced": 3,

    # Moderately negative words
    "uncertain": -3, "sell": -5, "decline": -5, "weakening": -5, "falling": -4,

    # Highly negative words
    "negative": -7, "bearish": -10, "pessimistic": -10, "crashing": -9, "collapsing": -9,
    "shrinking": -8, "decreasing": -8, "volatile": -7, "slowing": -6
}


# Giphy API key (you need to replace this with your own Giphy API key)
def extract_sentiments(text):
    # Split the text into words and filter out the sentiment-related words
    words = re.findall(r'\b\w+\b', text.lower())  # Extract words, ignoring punctuation
    sentiments = [word for word in words if word in SENTIMENT_SCORES]
    return sentiments



# Function to compute the total sentiment score
def compute_sentiment_score(sentiment_words):
    if len(sentiment_words) == 0:
        return 0

    min_score = 10
    max_score = -10
    for word in SENTIMENT_SCORES:
        score = SENTIMENT_SCORES[word]
        min_score = min(score, min_score)
        max_score = max(score, max_score)

    score = sum(SENTIMENT_SCORES[word] for word in sentiment_words) / len(sentiment_words)
    return score, min_score, max_score


# Function to classify sentiment
def classify_sentiment(sentiment_text):
    words = sentiment_text.lower().split()
    for word in words:
        if word in GOOD_SENTIMENTS:
            return "good"
        elif word in BAD_SENTIMENTS:
            return "bad"
    return "neutral"


# Function to fetch GIF from Giphy based on sentiment
def get_gif_for_sentiment(sentiment):
    from flask import current_app

    from .models import DB_Gif

    TENOR_API_KEY = current_app.config.get("TENOR_API_KEY", None)
    if TENOR_API_KEY:
        try:
            url = f"https://tenor.googleapis.com/v2/search?q={sentiment}&key={TENOR_API_KEY}&client_key=TOTHEMOON&limit=8"
            response = requests.get(url)
            data = response.json()

            gif_first = data['results'][0]
            mp4 = gif_first['media_formats']['mp4']['url']

            print_g(" SENTIMENT " + sentiment)
            print_b(" MP4 => " + mp4)

            db_gif = DB_Gif.objects(external_uuid = gif_first['id']).first()
            # TODO Pass the gif and save it in our media gallery

            return data, mp4, "mp4"

        except Exception as e:
            print_exception(e, "CRASHED LOADING TENOR GIF")


    GIPHY_API_KEY = current_app.config.get("GIPHY_API_KEY", None)
    if not GIPHY_API_KEY:
        return None, None

    if sentiment == "good":
        query = "happy"
    elif sentiment == "bad":
        query = "sad"
    else:
        query = sentiment

    url = f"https://api.giphy.com/v1/gifs/search?api_key={GIPHY_API_KEY}&q={query}&limit=1"
    response = requests.get(url)
    data = response.json()

    if data['data']:
        gif_url = data['data'][0]['images']['original']['url']
        return data, gif_url, "gif"
    else:
        return None, "No GIF found.", None


# Function to parse the sentiment from text
def parse_sentiment(text):
    # Assuming the format is "sentiment: <sentiment>"
    pattern = r"Sentiment:\s*[*]*([A-Za-z]+)[*]*"

    # Search for the sentiment
    match = re.search(pattern, text)

    if match:
        sentiment = match.group(1)
        #print(f"Extracted sentiment: {sentiment}")

        sentiment_words = extract_sentiments(text)
        score = compute_sentiment_score(sentiment_words)
        return sentiment, score

    return None, None


# Main function
def main_test():
    # Example text
    text = input("Enter a sentence containing a stock market sentiment (e.g., 'sentiment: bullish'): ")

    sentiment = parse_sentiment(text)
    if sentiment:
        sentiment_classification = classify_sentiment(sentiment)
        print(f"Sentiment classified as: {sentiment_classification}")

        # Get a GIF for the sentiment
        gif_url = get_gif_for_sentiment(sentiment_classification)
        print(f"GIF URL: {gif_url}")
    else:
        print("No valid sentiment found in the text.")

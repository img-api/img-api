import os
import re

import requests
import requests_cache

import pandas as pd
import yfinance as yf

from datetime import timedelta

from api.print_helper import *
from api.query_helper import *

from urllib.request import urlopen, Request
from bs4 import BeautifulSoup


def save_html_to_file(html_content, file_name, folder='downloaded_html'):
    # Create the folder if it doesn't exist
    if not os.path.exists(folder):
        os.makedirs(folder)

    # Define the full file path
    file_path = os.path.join(folder, file_name)

    # Save the raw HTML content to the file
    with open(file_path, 'wb') as file:  # 'wb' mode for writing bytes
        file.write(html_content)

    print(f"Saved HTML to {file_path}")


def get_html(url):
    headers = {
        'accept': 'application/html, text/plain, */*',
        'user-agent':
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36',
        'sec-fetch-site': 'same-site',
        'sec-fetch-mode': 'cors',
        'sec-fetch-dest': 'empty',
        'accept-language': 'en-US,en;q=0.9',
    }

    req = Request(url=url, headers=headers)
    response = urlopen(req)
    html = response.read()

    soup = BeautifulSoup(response, "html.parser")
    return soup, html

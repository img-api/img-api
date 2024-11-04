import os
import re
from datetime import timedelta
from urllib.request import Request, urlopen

import requests
import requests_cache
from api.print_helper import *
from api.query_helper import *
from bs4 import BeautifulSoup


def get_webdriver(driver=None):
    if driver:
        return driver

    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service as ChromeService

    chrome_executable_path = "./chrome/chrome/linux-128.0.6613.86/chrome-linux64/chrome"
    chromedriver_path = "./chrome/chromedriver-linux64/chromedriver"

    # Step 1: Setup Chrome options
    chrome_options = Options()
    chrome_options.binary_location = chrome_executable_path  # Specify the location of the Chrome binary

    chrome_options.add_argument("--headless")  # Optional, run Chrome in headless mode
    chrome_options.add_argument("--disable-gpu")  # Optional, disable GPU acceleration
    chrome_options.add_argument("--window-size=1920,1200")  # Optional, set window size

    # Step 2: Initialize the Chrome WebDriver

    # We have the driver in our system
    driver = webdriver.Chrome(service=ChromeService(chromedriver_path), options=chrome_options)

    return driver


def selenium_integration_test():

    driver = get_webdriver()

    # Step 3: Load a blank page
    driver.get("data:text/html,<html><head></head><body></body></html>")

    # Your HTML content in memory
    html_content = """
    <html>
    <head><title>Test HTML</title></head>
    <body>
        <h1>Hello, Selenium!</h1>
        <p>This is a paragraph in your HTML content.</p>
        <button id="myButton" onclick="alert('Button clicked!')">Click Me!</button>
    </body>
    </html>
    """

    # Step 4: Inject the HTML content into the blank page
    driver.execute_script("document.body.innerHTML = arguments[0];", html_content)

    # Step 5: Process the injected HTML
    # Example: Find and click the button
    button = driver.find_element("id", "myButton")
    button.click()

    # Handle alert if any
    alert = driver.switch_to.alert

    test_text = alert.text
    print(f"Alert text: {test_text}")

    alert.accept()

    # Step 6: Quit the driver
    driver.quit()

    if test_text == "Button clicked!":
        return True

    return False

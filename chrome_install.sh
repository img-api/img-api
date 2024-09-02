#!/bin/bash

mkdir chrome
cd chrome
npx @puppeteer/browsers install chrome@128.0.6613.86 -y
wget https://storage.googleapis.com/chrome-for-testing-public/128.0.6613.86/linux64/chromedriver-linux64.zip -O chromedriver-linux64.zip

unzip chromedriver-linux64.zip
#!/usr/bin/env bash

cd "${BASH_SOURCE%/*}"

sudo apt update
sudo apt install software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.9

python3 --version

echo "VIRTUAL ENV INSTALL"

sudo apt-get install python3-venv    # If needed
python3 -m venv .venv
source .venv/bin/activate

echo "MONGODB INSTALL"
sudo apt-get install mongodb-org

echo "START MONGO"
sudo systemctl start mongodb
sudo systemctl status mongodb

echo "IMAGE MAGICK"
sudo apt install imagemagick

echo "IMAGE MAGICK"
sudo apt install redis

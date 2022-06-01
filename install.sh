#!/usr/bin/env bash

cd "${BASH_SOURCE%/*}"

sudo apt update
sudo apt install software-properties-common  -y

echo "VIRTUAL ENV INSTALL"

sudo apt-get install python3-pip python3-venv -y   # If needed
python3 -m venv .venv
source .venv/bin/activate

echo "MONGODB INSTALL"
sudo apt-get install mongodb-org -y

echo "START MONGO"
sudo systemctl start mongod
sudo systemctl status mongod

echo "IMAGE MAGICK"
sudo apt install imagemagick -y

echo "IMAGE MAGICK"
sudo apt install redis -y

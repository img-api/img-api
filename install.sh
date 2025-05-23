#!/usr/bin/env bash

cd "${BASH_SOURCE%/*}"

sudo apt update
sudo apt install software-properties-common  -y

echo "VIRTUAL ENV INSTALL"

sudo apt-get install python3-pip python3-venv python3-dev python3-wheel -y   # If needed
sudo apt-get install libxml2-dev libxslt-dev unzip -y
sudo apt-get install python3-tk -y
sudi apt-get install libapache2-mod-wsgi-py3 -y
sudo apt-get install gunicorn -y

python3 -m venv .venv
source .venv/bin/activate

echo "MONGODB INSTALL"
curl -fsSL https://www.mongodb.org/static/pgp/server-4.4.asc | sudo apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/4.4 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-4.4.list
sudo apt update

sudo apt-get install mongodb-org -y

echo "START MONGO"
sudo systemctl start mongod
sudo systemctl status mongod
sudo systemctl enable mongod

echo "IMAGE MAGICK"
sudo apt install imagemagick -y

echo "REDIS"
sudo apt install redis -y

echo "DOCKER"
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh ./get-docker.sh

echo "CHROMA"
sudo docker run -d --rm --name chromadb -p 8000:8000 -v ./chroma:/chroma/chroma -e IS_PERSISTENT=TRUE -e ANONYMIZED_TELEMETRY=TRUE chromadb/chroma:0.6.3


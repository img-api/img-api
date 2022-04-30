#!/usr/bin/env bash

cd "${BASH_SOURCE%/*}"

echo "VIRTUAL ENV INSTALL"

sudo apt-get install python3-venv    # If needed
python3 -m venv .venv
source .venv/bin/activate

echo "MONGODB INSTALL"
sudo apt-get install mongodb-org
#!/bin/sh

python3 -m virtualenv .venv --python=python3

echo "UPDATING IMG-API"

cd "${BASH_SOURCE%/*}"

. .venv/bin/activate

pip3 install -r requirements.txt --upgrade


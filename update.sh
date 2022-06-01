#!/bin/bash

if [ ! -d ".venv" ]
then
   echo "INSTALLING VENV "
   python3 -m venv .venv
fi

echo "UPDATING IMG-API"

cd "${BASH_SOURCE%/*}"

. .venv/bin/activate

pip3 install -r requirements.txt --upgrade


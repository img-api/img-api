#!/bin/bash

cd "${BASH_SOURCE%/*}"

export LC_ALL=C.UTF-8
export LANG=C.UTF-8

. .venv/bin/activate

if [ -n "${IMGAPI_SETTINGS}" ]; then
    echo "Settings found"
else
    echo "No production settings setup"
    relative_path=".img-api/development_settings.cfg"
    export IMGAPI_SETTINGS="$(realpath "$HOME/$relative_path")"
    echo $IMGAPI_SETTINGS
fi

echo "Running flask!"
export FLASK_DEBUG=1
export FLASK_APP=imgapi_launcher.py
export FLASK_PORT=5111

pip3 install yfinance --upgrade

while true; do
    echo " "
    echo "------------------------------"
    echo "------------ LAUNCH ----------"
    echo "------------------------------"
    echo " "

    flask run --host=0.0.0.0 -p $FLASK_PORT --with-threads
    sleep 10s
done

$SHELL

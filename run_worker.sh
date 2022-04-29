#!/bin/bash

cd "${BASH_SOURCE%/*}"

export LC_ALL=C.UTF-8
export LANG=C.UTF-8

. .venv/bin/activate

cd services

while true; do
    echo " "
    echo "------------------------------"
    echo "------------ WORKER ----------"
    echo "------------------------------"
    echo " "
    python worker.py
done

$SHELL

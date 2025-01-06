#!/bin/bash

cd "${BASH_SOURCE%/*}"

. .venv/bin/activate

python services/telegram/service_fetch.py

$SHELL

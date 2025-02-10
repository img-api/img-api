#!/bin/bash

cd "${BASH_SOURCE%/*}" || exit 1  # Ensure script runs in its directory

export LC_ALL=C.UTF-8
export LANG=C.UTF-8

. .venv/bin/activate  # Activate virtual environment

gunicorn --workers 4 --threads 8 \
  --bind 0.0.0.0:8001 \
  --chdir "$(pwd)" \
  --pythonpath "$(pwd)/.venv/lib/python3.11/site-packages" \
  imgapi_launcher:app
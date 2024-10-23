#!/bin/bash

cd "${BASH_SOURCE%/*}"

export LC_ALL=C.UTF-8
export LANG=C.UTF-8

. .venv/bin/activate

if [ -n "${IMGAPI_SETTINGS}" ]; then
    echo "Settings found"
else
    echo "Developer settings setup"
    relative_path=".img-api/development_settings.cfg"
    export IMGAPI_SETTINGS="$(realpath "$HOME/$relative_path")"

    echo $IMGAPI_SETTINGS
fi


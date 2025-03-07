#!/bin/bash

SCRIPT_DIR="$(dirname "$(realpath "$BASH_SOURCE")")"

cd "$SCRIPT_DIR" || exit 1

echo "$SCRIPT_DIR"

tmux new-session -d -s my_server "$SCRIPT_DIR/start_gunicorn.sh"
tmux split-window -h -t my_server "$SCRIPT_DIR/run.sh"
tmux split-window -hf -t my_server "bash"

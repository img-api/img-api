#!/bin/bash
# Restart (or start) the dev stack.
cd "$(dirname "$0")" && pm2 startOrRestart ecosystem.dev.config.cjs --update-env && pm2 save

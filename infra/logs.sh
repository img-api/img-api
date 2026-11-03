#!/bin/bash
pm2 logs --lines 100 img-api-dev-api img-api-dev-ui "$@"

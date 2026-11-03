#!/bin/bash
pm2 ls | grep -E 'name|img-api-dev'
curl -s -o /dev/null -w 'api  %{http_code}\n' http://127.0.0.1:5112/api/hello_world/
curl -s -o /dev/null -w 'ui   %{http_code}\n' http://127.0.0.1:47131/
curl -s -o /dev/null -w 'site %{http_code}\n' https://dev.img-api.com/

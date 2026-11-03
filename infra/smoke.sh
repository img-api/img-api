#!/bin/bash
# Read-only smoke test of an img-api instance.
#
#   infra/smoke.sh https://img-api.com            public site (frontend + API)
#   infra/smoke.sh http://127.0.0.1:47120 --api   gunicorn directly (API only)
#
# Exit code 0 when every check passes.
set -uo pipefail

BASE="${1:?usage: smoke.sh <base-url> [--api]}"
API_ONLY="${2:-}"
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
ok=1

check() {  # path expected_status [grep]
    local code
    code=$(curl -s -o "$TMP" -w '%{http_code}' --max-time 20 "$BASE$1")
    if [ "$code" != "$2" ] || { [ -n "${3:-}" ] && ! grep -q "$3" "$TMP"; }; then
        echo "  FAIL $1 -> $code (expected $2${3:+ and '$3'})"
        ok=0
        return 1
    fi
    echo "  ok   $1 -> $code"
}

check /api/hello_world/ 200 '"hello world"'
check /api/user/get/me 401
check /api/galleries/public/get 200 '"success"'
if check /api/media/category/NEW 200 '"success"'; then
    # The newest media must redirect to its file under /static/MEDIA_FILES
    MEDIA_ID=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["media_files"][0]["media_id"])' "$TMP" 2>/dev/null || true)
    if [ -n "$MEDIA_ID" ]; then
        check "/api/media/get/$MEDIA_ID" 302
        check "/api/media/posts/$MEDIA_ID/get" 200 '"success"'
    else
        echo "  FAIL no media in /api/media/category/NEW"
        ok=0
    fi
fi
if [ "$API_ONLY" != "--api" ]; then
    check / 200 'id="root"'
fi

[ "$ok" = 1 ]

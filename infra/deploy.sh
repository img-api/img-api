#!/bin/bash
# Deploy img-api.com from a pushed branch: API (gunicorn) + React frontend.
#
#   infra/deploy.sh [branch]        (default: main, for both repos)
#
# One-time setup first: infra/PROD_MIGRATION.md
# Each step stops the deploy on failure; the live site only changes at the
# "switch" steps, and the script prints how to roll back.
set -euo pipefail

BRANCH="${1:-main}"
PROD=/home/imgapi/img-api
RELEASE=/home/imgapi/img-api-react-release/build
UI_REPO=/home/smartinez/img-api-react
NODE_BIN=/home/smartinez/.nvm/versions/node/v22.23.4/bin
SERVICE=img-api
PORT=47120
SITE=https://img-api.com
STAMP=$(date +%Y%m%d-%H%M%S)

AS_IMGAPI="sudo -u imgapi -H"
GIT="$AS_IMGAPI git -C $PROD"

say()  { printf '\n== %s\n' "$*"; }
fail() { printf '\nDEPLOY STOPPED: %s\n' "$*" >&2; exit 1; }

# --- Preflight ---------------------------------------------------------------
say "Preflight"
systemctl cat "$SERVICE" >/dev/null 2>&1 || fail "systemd unit '$SERVICE' is not installed. See infra/PROD_MIGRATION.md step 1."

if [ -n "$($GIT status --porcelain --untracked-files=no)" ]; then
    $GIT status --short --untracked-files=no | head -20 >&2
    fail "prod git in $PROD has uncommitted changes (above). Commit them to the repo or stash them on prod first (PROD_MIGRATION.md step 0). Nothing was changed."
fi

PREV_SHA=$($GIT rev-parse HEAD)
PREV_VENV=$(readlink -f "$PROD/.venv-current" 2>/dev/null || true)

# --- Backend code ----------------------------------------------------------------
say "Backend: fast-forward $PROD to origin/$BRANCH"
$GIT fetch -q origin
$GIT checkout -q "$BRANCH"
$GIT merge -q --ff-only "origin/$BRANCH" || fail "origin/$BRANCH is not a fast-forward of prod's $BRANCH."
NEW_SHA=$($GIT rev-parse --short HEAD)

# --- Backend venv + tests (live site untouched) --------------------------------
VENV="$PROD/.venv-$STAMP-$NEW_SHA"
say "Backend: new venv $VENV"
$AS_IMGAPI python3.11 -m venv "$VENV"
$AS_IMGAPI "$VENV/bin/pip" install -q --upgrade pip
$AS_IMGAPI "$VENV/bin/pip" install -q -r "$PROD/requirements.txt"

say "Backend: tests (throwaway database imgapi_pytest)"
(cd "$PROD" && $AS_IMGAPI "$VENV/bin/python" -m pytest -q -p no:cacheprovider) || {
    $GIT checkout -q "$PREV_SHA"
    fail "tests failed; prod code reset to $PREV_SHA, live API untouched."
}

# --- Frontend build (live site untouched) ---------------------------------------
BUILD_DIR=$(mktemp -d /tmp/img-api-ui-XXXXXX)
say "Frontend: build origin/$BRANCH in $BUILD_DIR"
git -C "$UI_REPO" fetch -q origin
git -C "$UI_REPO" worktree add -q --detach "$BUILD_DIR" "origin/$BRANCH"
trap 'git -C "$UI_REPO" worktree remove --force "$BUILD_DIR" 2>/dev/null || true' EXIT
(
    cd "$BUILD_DIR"
    export PATH="$NODE_BIN:$PATH"
    npm ci --silent
    npx vite build
)
[ -f "$BUILD_DIR/build/index.html" ] || fail "frontend build produced no build/index.html"

# --- Switch: API -----------------------------------------------------------------
say "Switch API to $VENV"
sudo ln -sfn "$VENV" "$PROD/.venv-current"
sudo chown -h imgapi:imgapi "$PROD/.venv-current"
sudo systemctl restart "$SERVICE"
for _ in $(seq 1 30); do
    curl -sf -o /dev/null "http://127.0.0.1:$PORT/api/hello_world/" && break
    sleep 1
done
curl -sf -o /dev/null "http://127.0.0.1:$PORT/api/hello_world/" || fail "API did not come up on :$PORT. Roll back: see below."

# --- Switch: frontend ------------------------------------------------------------
say "Switch frontend (backup: $RELEASE.prev-$STAMP)"
sudo cp -a "$RELEASE" "$RELEASE.prev-$STAMP"
sudo rsync -a --delete "$BUILD_DIR/build/" "$RELEASE/"
sudo chown -R imgapi:imgapi "$RELEASE"

# --- Smoke test the public site --------------------------------------------------
say "Smoke test $SITE"
check() {  # url expected_status [grep]
    local code
    code=$(curl -s -o /tmp/img-api-smoke.$$ -w '%{http_code}' "$SITE$1")
    if [ "$code" != "$2" ] || { [ -n "${3:-}" ] && ! grep -q "$3" /tmp/img-api-smoke.$$; }; then
        echo "  FAIL $1 -> $code (expected $2${3:+ and '$3'})"; return 1
    fi
    echo "  ok   $1 -> $code"
}
ok=1
check /api/hello_world/ 200 '"hello world"' || ok=0
check /api/user/get/me 401 || ok=0
check /api/media/category/NEW 200 '"success"' || ok=0
check /api/galleries/public/get 200 '"success"' || ok=0
check / 200 'id="root"' || ok=0
rm -f /tmp/img-api-smoke.$$

# Keep the 3 newest venvs
ls -dt "$PROD"/.venv-2* 2>/dev/null | tail -n +4 | xargs -r sudo rm -rf

cat <<EOF

Roll back if needed:
  sudo -u imgapi git -C $PROD checkout $PREV_SHA
  ${PREV_VENV:+sudo ln -sfn $PREV_VENV $PROD/.venv-current && }sudo systemctl restart $SERVICE
  sudo rsync -a --delete $RELEASE.prev-$STAMP/ $RELEASE/
EOF

[ "$ok" = 1 ] || fail "smoke test failed (see above)."
say "Deployed $NEW_SHA ($BRANCH)"

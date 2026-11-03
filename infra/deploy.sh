#!/bin/bash
# Deploy img-api.com from a pushed branch: API (gunicorn) + React frontend.
#
#   infra/deploy.sh [branch]        (default: main, for both repos)
#
# One-time setup first: infra/PROD_MIGRATION.md
#
# Safety: nothing here touches media files or the database. If any step fails,
# the script rolls back whatever it already changed (code, venv, frontend) and
# says so. The live site only changes at the two "Switch" steps.
set -euo pipefail

BRANCH="${1:-main}"
# Overridable only so the script can be rehearsed in a sandbox (see infra/test_deploy.sh)
PROD=${DEPLOY_PROD:-/home/imgapi/img-api}
RELEASE=${DEPLOY_RELEASE:-/home/imgapi/img-api-react-release/build}
UI_REPO=${DEPLOY_UI_REPO:-/home/smartinez/img-api-react}
UI_REF=${DEPLOY_UI_REF:-origin/$BRANCH}
NODE_BIN=/home/smartinez/.nvm/versions/node/v22.23.4/bin
SERVICE=img-api
PORT=${DEPLOY_PORT:-47120}
SITE=${DEPLOY_SITE:-https://img-api.com}
SUDO=${DEPLOY_SUDO-sudo}
SYSTEMCTL=${DEPLOY_SYSTEMCTL-sudo systemctl}
OWNER=${DEPLOY_OWNER-imgapi:imgapi}
SMOKE="$(dirname "$(realpath "$0")")/smoke.sh"
STAMP=$(date +%Y%m%d-%H%M%S)
KEEP_VENVS=3
KEEP_UI_BACKUPS=5

AS_IMGAPI=${DEPLOY_AS-sudo -u imgapi -H}
GIT="$AS_IMGAPI git -C $PROD"

say() { printf '\n== %s\n' "$*"; }
set_owner() {  # flag path
    [ -z "$OWNER" ] && return 0
    $SUDO chown "$1" "$OWNER" "$2"
}

# --- Rollback ------------------------------------------------------------------
# Each stage records what it changed; on any failure we undo it in reverse.
CODE_CHANGED=0
VENV=""
API_SWITCHED=0
UI_SWITCHED=0
UI_BACKUP=""
BUILD_DIR=""
DONE=0

restore_code() {
    if [ -n "$PREV_BRANCH" ]; then
        $GIT checkout -q "$PREV_BRANCH" && $GIT reset -q --keep "$PREV_SHA"
    else
        $GIT checkout -q "$PREV_SHA"
    fi
}

on_exit() {
    local status=$?
    [ -n "$BUILD_DIR" ] && git -C "$UI_REPO" worktree remove --force "$BUILD_DIR" 2>/dev/null || true
    if [ "$DONE" = 1 ]; then return; fi
    if [ "$CODE_CHANGED" = 0 ]; then echo "Nothing was changed." >&2; return; fi
    set +e
    printf '\nDEPLOY FAILED (exit %s). Rolling back:\n' "$status" >&2
    if [ "$UI_SWITCHED" = 1 ]; then
        $SUDO rsync -a --delete "$UI_BACKUP/" "$RELEASE/" && echo "  frontend restored from $UI_BACKUP" >&2
    fi
    if [ "$API_SWITCHED" = 1 ]; then
        if [ -n "$PREV_VENV" ]; then
            $SUDO ln -sfn "$PREV_VENV" "$PROD/.venv-current" && set_owner -h "$PROD/.venv-current"
        else
            $SUDO rm -f "$PROD/.venv-current"   # first deploy: there was no previous venv
        fi
    fi
    if [ "$CODE_CHANGED" = 1 ]; then
        restore_code && echo "  code restored to $PREV_SHA" >&2
    fi
    if [ "$API_SWITCHED" = 1 ]; then
        if [ -n "$PREV_VENV" ]; then
            $SYSTEMCTL restart "$SERVICE" && echo "  API restarted on $PREV_VENV" >&2
        else
            $SYSTEMCTL stop "$SERVICE" && echo "  first deploy: gunicorn stopped (Apache/mod_wsgi untouched)" >&2
        fi
    fi
    if [ -n "$VENV" ] && [ "$(readlink -f "$PROD/.venv-current" 2>/dev/null)" != "$VENV" ]; then
        $SUDO rm -rf "$VENV" && echo "  removed unused venv $VENV" >&2
    fi
    echo "  Nothing in media files or the database was touched." >&2
}
trap on_exit EXIT

# --- Preflight -------------------------------------------------------------------
say "Preflight"
$SYSTEMCTL cat "$SERVICE" >/dev/null 2>&1 || { echo "systemd unit '$SERVICE' is not installed. See infra/PROD_MIGRATION.md step 1." >&2; exit 1; }

if [ -n "$($GIT status --porcelain --untracked-files=no)" ]; then
    $GIT status --short --untracked-files=no | head -20 >&2
    echo "prod git in $PROD has uncommitted changes (above). Stash them first (PROD_MIGRATION.md step 0). Nothing was changed." >&2
    exit 1
fi

PREV_SHA=$($GIT rev-parse HEAD)
PREV_BRANCH=$($GIT symbolic-ref -q --short HEAD || true)
PREV_VENV=$(readlink -f "$PROD/.venv-current" 2>/dev/null || true)

# --- Backend code --------------------------------------------------------------------
say "Backend: fast-forward $PROD to origin/$BRANCH"
$GIT fetch -q origin
CODE_CHANGED=1
$GIT checkout -q "$BRANCH"
$GIT merge -q --ff-only "origin/$BRANCH"
NEW_SHA=$($GIT rev-parse --short HEAD)

# --- Backend venv + tests (live site untouched) ----------------------------------
VENV="$PROD/.venv-$STAMP-$NEW_SHA"
say "Backend: new venv $VENV"
$AS_IMGAPI python3.11 -m venv "$VENV"
$AS_IMGAPI "$VENV/bin/pip" install -q --upgrade pip
$AS_IMGAPI "$VENV/bin/pip" install -q -r "$PROD/requirements.txt"

say "Backend: tests (throwaway database imgapi_pytest)"
(cd "$PROD" && $AS_IMGAPI "$VENV/bin/python" -m pytest -q -p no:cacheprovider)

# --- Frontend build (live site untouched) -----------------------------------------
BUILD_DIR=$(mktemp -d /tmp/img-api-ui-XXXXXX)
say "Frontend: build $UI_REF in $BUILD_DIR"
[ "${DEPLOY_UI_FETCH:-1}" = 1 ] && git -C "$UI_REPO" fetch -q origin
git -C "$UI_REPO" worktree add -q --detach --force "$BUILD_DIR" "$UI_REF"
(
    cd "$BUILD_DIR"
    export PATH="$NODE_BIN:$PATH"
    npm ci --silent
    npx vite build
)
[ -f "$BUILD_DIR/build/index.html" ] || { echo "frontend build produced no build/index.html" >&2; exit 1; }

# --- Switch: API -------------------------------------------------------------------
say "Switch API to $VENV"
API_SWITCHED=1
$SUDO ln -sfn "$VENV" "$PROD/.venv-current"
set_owner -h "$PROD/.venv-current"
$SYSTEMCTL restart "$SERVICE"
for _ in $(seq 1 30); do
    curl -sf -o /dev/null "http://127.0.0.1:$PORT/api/hello_world/" && break
    sleep 1
done
say "Smoke test gunicorn directly (127.0.0.1:$PORT)"
"$SMOKE" "http://127.0.0.1:$PORT" --api

# --- Switch: frontend --------------------------------------------------------------
UI_BACKUP="$RELEASE.prev-$STAMP"
say "Switch frontend (backup: $UI_BACKUP)"
$SUDO cp -a "$RELEASE" "$UI_BACKUP"
UI_SWITCHED=1
$SUDO rsync -a --delete "$BUILD_DIR/build/" "$RELEASE/"
set_owner -R "$RELEASE"

# --- Smoke test the public site ----------------------------------------------------
say "Smoke test $SITE"
"$SMOKE" "$SITE"

DONE=1

# --- Housekeeping (never removes the live or the previous venv / frontend) ----------
LIVE_VENV=$(readlink -f "$PROD/.venv-current")
prune() {  # keep pattern protected...: delete all but the newest <keep>, never the protected paths
    local keep=$1 pattern=$2; shift 2
    local path
    for path in $(ls -dt $pattern 2>/dev/null | tail -n +$((keep + 1))); do
        case " $* " in *" $path "*) continue ;; esac
        $SUDO rm -rf "$path"
    done
}
prune "$KEEP_VENVS" "$PROD/.venv-2*" "$LIVE_VENV" "${PREV_VENV:-}"
prune "$KEEP_UI_BACKUPS" "$RELEASE.prev-*" "$UI_BACKUP"

cat <<EOF

Deployed $NEW_SHA ($BRANCH).
Roll back by hand if something shows up later:
  sudo -u imgapi git -C $PROD checkout ${PREV_BRANCH:-$PREV_SHA}${PREV_BRANCH:+ && sudo -u imgapi git -C $PROD reset --keep $PREV_SHA}
  ${PREV_VENV:+$SUDO ln -sfn $PREV_VENV $PROD/.venv-current && }$SYSTEMCTL restart $SERVICE
  $SUDO rsync -a --delete $UI_BACKUP/ $RELEASE/
EOF

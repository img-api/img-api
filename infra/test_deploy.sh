#!/bin/bash
# Rehearses infra/deploy.sh in a sandbox: a throwaway clone stands in for
# /home/imgapi/img-api, a temp folder for the frontend release, and the dev
# stack (dev.img-api.com, API on :5112) answers the smoke tests. systemctl is
# replaced by echo. Prod is never touched.
#
#   infra/test_deploy.sh            (takes a few minutes: builds venvs + frontend)
set -uo pipefail

HERE="$(dirname "$(realpath "$0")")"
REPO="$(dirname "$HERE")"
SB=$(mktemp -d /tmp/img-api-deploy-test-XXXXXX)
trap 'rm -rf "$SB"' EXIT
BRANCH=modernize
fails=0

pass() { echo "  PASS $*"; }
bad()  { echo "  FAIL $*"; fails=$((fails + 1)); }
expect_eq() { [ "$1" = "$2" ] && pass "$3" || bad "$3 (got '$1', want '$2')"; }

git clone -q --bare "$REPO" "$SB/remote.git"
git clone -q "$SB/remote.git" "$SB/prod"
git -C "$SB/prod" checkout -q "$BRANCH"
git -C "$SB/prod" reset -q --hard "$BRANCH~1"   # prod is one commit behind
mkdir -p "$SB/release"
echo OLD > "$SB/release/index.html"

export DEPLOY_PROD="$SB/prod" DEPLOY_RELEASE="$SB/release" DEPLOY_UI_REF="$BRANCH" DEPLOY_UI_FETCH=0
export DEPLOY_PORT=5112 DEPLOY_SITE=https://dev.img-api.com
export DEPLOY_AS="" DEPLOY_SUDO="" DEPLOY_OWNER="" DEPLOY_SYSTEMCTL="echo [systemctl]"

push_commit() {  # message [file content]
    local work="$SB/work"
    rm -rf "$work" && git clone -q "$SB/remote.git" "$work" && git -C "$work" checkout -q "$BRANCH"
    if [ -n "${2:-}" ]; then printf '%s\n' "$2" > "$work/test/unit/apiapp/test_zz_deploy_rehearsal.py"; else date > "$work/infra/.rehearsal"; fi
    git -C "$work" add -A && git -C "$work" -c user.name=rehearsal -c user.email=r@x commit -q -m "$1" && git -C "$work" push -q origin "$BRANCH"
}

venvs() { ls -d "$SB/prod"/.venv-2* 2>/dev/null | wc -l; }

echo "== 0: first deploy fails after the API switch -> no venv link left behind"
P0_SHA=$(git -C "$SB/prod" rev-parse HEAD)
DEPLOY_PORT=59999 "$HERE/deploy.sh" "$BRANCH" > "$SB/0.log" 2>&1
[ "$?" != 0 ] && pass "deploy exits non-zero" || bad "deploy should fail"
[ ! -e "$SB/prod/.venv-current" ] && pass "no .venv-current left" || bad ".venv-current left behind"
expect_eq "$(venvs)" 0 "failed venv removed"
expect_eq "$(git -C "$SB/prod" rev-parse HEAD)" "$P0_SHA" "code back to where it was"
expect_eq "$(cat "$SB/release/index.html")" OLD "frontend untouched"

echo "== A: normal deploy"
"$HERE/deploy.sh" "$BRANCH" > "$SB/a.log" 2>&1
expect_eq "$?" 0 "deploy exits 0"
A_SHA=$(git -C "$SB/prod" rev-parse HEAD)
A_VENV=$(readlink -f "$SB/prod/.venv-current")
expect_eq "$A_SHA" "$(git -C "$SB/remote.git" rev-parse "$BRANCH")" "prod code is at the branch tip"
[ -x "$A_VENV/bin/gunicorn" ] && pass "live venv has gunicorn" || bad "live venv missing"
grep -q 'id="root"' "$SB/release/index.html" && pass "frontend replaced by the new build" || bad "frontend not replaced"
A_INDEX=$(md5sum < "$SB/release/index.html")

echo "== B: public smoke test fails after both switches -> full rollback"
push_commit "rehearsal: harmless change"
DEPLOY_SITE=https://dev.img-api.com/__no_such_prefix "$HERE/deploy.sh" "$BRANCH" > "$SB/b.log" 2>&1
[ "$?" != 0 ] && pass "deploy exits non-zero" || bad "deploy should fail"
expect_eq "$(git -C "$SB/prod" rev-parse HEAD)" "$A_SHA" "code back to A"
expect_eq "$(readlink -f "$SB/prod/.venv-current")" "$A_VENV" "venv back to A"
expect_eq "$(md5sum < "$SB/release/index.html")" "$A_INDEX" "frontend back to A"
expect_eq "$(venvs)" 1 "B's venv removed"
grep -q "Rolling back" "$SB/b.log" && pass "log says it rolled back" || bad "no rollback message"

echo "== C: tests fail -> code rolled back, nothing switched"
push_commit "rehearsal: failing test" "def test_rehearsal_fails():
    assert False, 'deploy rehearsal'"
"$HERE/deploy.sh" "$BRANCH" > "$SB/c.log" 2>&1
[ "$?" != 0 ] && pass "deploy exits non-zero" || bad "deploy should fail"
expect_eq "$(git -C "$SB/prod" rev-parse HEAD)" "$A_SHA" "code back to A"
expect_eq "$(readlink -f "$SB/prod/.venv-current")" "$A_VENV" "venv still A"
expect_eq "$(md5sum < "$SB/release/index.html")" "$A_INDEX" "frontend untouched"
expect_eq "$(venvs)" 1 "C's venv removed"
grep -q "\[systemctl\] restart" "$SB/c.log" && bad "API was restarted" || pass "API never restarted"

echo "== D: dirty prod tree -> refuses, changes nothing"
echo "# local hotfix" >> "$SB/prod/imgapi_launcher.py"
"$HERE/deploy.sh" "$BRANCH" > "$SB/d.log" 2>&1
[ "$?" != 0 ] && pass "deploy refuses" || bad "deploy should refuse"
grep -q "Nothing was changed" "$SB/d.log" && pass "says nothing changed" || bad "missing 'Nothing was changed'"
expect_eq "$(git -C "$SB/prod" rev-parse HEAD)" "$A_SHA" "code untouched"

if [ "$fails" != 0 ]; then
    echo; echo "$fails check(s) failed. Logs:"; for f in 0 a b c d; do echo "--- $f"; tail -25 "$SB/$f.log"; done
    exit 1
fi
echo; echo "All deploy rehearsal checks passed."

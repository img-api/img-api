# Moving prod from mod_wsgi to gunicorn (one time)

Today img-api.com runs the API inside Apache (mod_wsgi, Python 3.10,
`/home/imgapi/img-api/.venv310`). The modernised code needs Python 3.11, which
mod_wsgi can't load (it is built for the system Python 3.10). So prod moves to
gunicorn behind Apache, the same way dev.img-api.com already runs.

Nothing here has been done yet. Each step is reversible.

## 0. Fix prod's git first

`/home/imgapi/img-api` has a broken git state: HEAD is a commit called
"no idea" on a 2024 base, 272 commits behind origin, with a big staged diff
that brings the files back to roughly origin/main. Its files match the repo
(plus the hot-fixes now committed). Once the branch is pushed:

    sudo -u imgapi git -C /home/imgapi/img-api stash push -m "pre-reset state"   # keeps everything
    sudo -u imgapi git -C /home/imgapi/img-api fetch origin
    sudo -u imgapi git -C /home/imgapi/img-api checkout -B main origin/main

`infra/deploy.sh` refuses to run while prod's git has uncommitted changes.

## 0b. New SECRET_KEY (urgent, can be done on its own today)

Prod signs login tokens with the key that was committed to the public repo, so
anyone can forge a token for any user, admin included. The new code refuses to
start with that key. Rotating it logs everyone out once (tokens are re-issued
at the next login):

    sudo -u imgapi python3 - <<'PY'
    import json, os, secrets
    p = '/home/imgapi/.imgapi.json'
    d = json.load(open(p)); d['SECRET_KEY'] = secrets.token_urlsafe(48)
    json.dump(d, open(p, 'w'), indent=4); os.chmod(p, 0o600)
    PY
    sudo systemctl reload apache2      # mod_wsgi picks up the new key

Any other client holding a token (the Telegram bot) needs a fresh one.

## 1. Install the service (does not affect the live site)

    sudo cp /home/smartinez/img-api/infra/img-api.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable img-api

Rehearse the deploy script first (sandbox, never touches prod):
`infra/test_deploy.sh`. Then run the first deploy: `infra/deploy.sh main`.
If any step fails, the script rolls back what it changed (code, venv, frontend)
by itself and says so; it never touches media files or the database. It creates the venv,
starts gunicorn on 127.0.0.1:47120 and updates the frontend. Apache still
serves the API through mod_wsgi until step 2, which now loads the new code
from the old Python 3.10 venv the next time Apache restarts its processes.
So do step 2 right after the first deploy, and don't reload Apache in
between.

## 2. Point Apache at gunicorn

In both `/etc/apache2/sites-enabled/024-imgapi.conf` and
`024-imgapi-le-ssl.conf`, replace the mod_wsgi block:

    WSGIPassAuthorization On
    WSGIDaemonProcess imgapi_launcher ... python-home=/home/imgapi/img-api/.venv310 ...
    WSGIProcessGroup imgapi_launcher
    WSGIScriptAlias /api /home/imgapi/img-api/imgapi_launcher.wsgi/api
    WSGIScriptReloading On
    <Files imgapi_launcher.wsgi> ... </Files>

with:

    ProxyPass        /api/ http://127.0.0.1:47120/api/
    ProxyPassReverse /api/ http://127.0.0.1:47120/api/
    # Password-reset links use request.scheme; gunicorn trusts this from 127.0.0.1
    RequestHeader set X-Forwarded-Proto "https"

(use "http" in the port-80 vhost). Keep the trailing slashes: without them
`/api` also matches `/api_v1/...`, which the vhost sends elsewhere. Keep `ProxyPreserveHost On`, the
`DocumentRoot` and the `Alias /static/MEDIA_FILES` block as they are: Apache
keeps serving the frontend and the media files directly.

Remove the inactive `024-imgapi*.conf.pre2204` copies while there.

Check gunicorn on its own first, then switch and check the public site:

    infra/smoke.sh http://127.0.0.1:47120 --api
    sudo apache2ctl configtest && sudo systemctl reload apache2
    infra/smoke.sh https://img-api.com

If the second smoke test fails, roll back (below) straight away.

Rollback: put the WSGI block back and reload. The old `.venv310` stays
untouched until you delete it.

## 3. After a few quiet days

- Delete `/home/imgapi/img-api/.venv310` and the old `.venv` (Python 3.8).
- `imgapi_launcher.wsgi` is no longer used.

## Notes

- `/etc/nginx/sites-enabled/imgapi.conf` is leftover: nginx isn't running and
  Apache owns ports 80 and 443 (checked 2026-11-03).
- Workers: mod_wsgi ran 4 processes x 256 threads. Gunicorn starts with 4 x 16.
  Large files never go through Python (Apache serves `/static/MEDIA_FILES`),
  so that should be plenty. Raise `--threads` in the unit if needed.

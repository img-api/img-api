# Development

## Dev stack: https://dev.img-api.com

Run by PM2 from `infra/ecosystem.dev.config.cjs`:

| process           | what                                         | where           |
|-------------------|----------------------------------------------|-----------------|
| `img-api-dev-api` | this repo, gunicorn with `--reload`          | 127.0.0.1:5112  |
| `img-api-dev-ui`  | `/home/smartinez/img-api-react`, Vite        | 127.0.0.1:47131 |

Apache serves `dev.img-api.com`: `/api/` goes to the API, `/static/MEDIA_FILES`
is served from disk, everything else goes to Vite (with hot reload).

    infra/restart.sh    # start or restart both
    infra/status.sh     # processes + HTTP checks
    infra/logs.sh       # tail both logs

Dev never touches prod data:

- Database `imgapi_dev` (a copy of prod's `test`), chosen by `~/.imgapi-dev.json`
  through `IMGAPI_CONFIG`.
- Media in `~/img-api-dev-data/media`: a hard-linked copy of
  `/home/imgapi/IMGAPI_DATA`. It takes no extra disk, and prod's files are
  read-only for us, so deleting or uploading in dev doesn't change prod.

## Tests

    .venv/bin/python -m pytest -q          # backend, throwaway database imgapi_pytest
    cd ../img-api-react && npx playwright test   # e2e against dev.img-api.com, phone + desktop
    infra/test_deploy.sh                   # rehearses the prod deploy in a sandbox

The Playwright run seeds an `e2e_owner` user with three posts in `imgapi_dev`
(and refuses any base URL that isn't dev).

## Deploying to img-api.com

See `infra/PROD_MIGRATION.md` (one-time move to gunicorn) and `infra/deploy.sh`.

## API

- Hello world: `/api/hello_world/`
- Newest public media: `/api/media/category/NEW`
- A post, with next/previous: `/api/media/posts/<id>/get?next=posts` (or `?next=<gallery>`)
- A media file: `/api/media/get/<id>` (redirects to `/static/MEDIA_FILES/...`),
  poster frame `/api/media/get/<id>.v512.JPG`

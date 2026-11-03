// Dev stack for dev.img-api.com (PM2, fork mode).
// Apache proxies dev.img-api.com -> UI (47131) and /api -> API (5112).
// Dev uses its own Mongo DB (imgapi_dev) and a hard-linked copy of prod media,
// so nothing here can change prod data or files.
const HOME = '/home/smartinez';

module.exports = {
  apps: [
    {
      name: 'img-api-dev-api',
      cwd: `${HOME}/img-api`,
      // Same server as prod will use (gunicorn); --reload restarts on code changes
      script: `${HOME}/img-api/.venv/bin/gunicorn`,
      args: '--bind 127.0.0.1:5112 --workers 2 --threads 8 --timeout 120 --reload imgapi_launcher:app',
      interpreter: 'none',
      exec_mode: 'fork',
      env: {
        IMGAPI_CONFIG: `${HOME}/.imgapi-dev.json`,
        IMGAPI_MEDIA_PATH: `${HOME}/img-api-dev-data/media/`,
        LC_ALL: 'C.UTF-8',
        LANG: 'C.UTF-8',
      },
    },
    {
      name: 'img-api-dev-ui',
      cwd: `${HOME}/img-api-react`,
      // Vite dev server; host/port/HMR settings live in img-api-react/vite.config.js
      script: 'node_modules/vite/bin/vite.js',
      interpreter: `${HOME}/.nvm/versions/node/v22.23.4/bin/node`,
      exec_mode: 'fork',
    },
  ],
};

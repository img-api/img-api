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
      script: `${HOME}/img-api/.venv/bin/flask`,
      args: 'run --host 127.0.0.1 -p 5112 --with-threads --no-debugger', // debugger off: reachable from the internet
      interpreter: 'none',
      exec_mode: 'fork',
      env: {
        FLASK_APP: 'imgapi_launcher.py',
        FLASK_DEBUG: '1',
        IMGAPI_CONFIG: `${HOME}/.imgapi-dev.json`,
        IMGAPI_MEDIA_PATH: `${HOME}/img-api-dev-data/media/`,
        LC_ALL: 'C.UTF-8',
        LANG: 'C.UTF-8',
      },
    },
    {
      name: 'img-api-dev-ui',
      cwd: `${HOME}/img-api-react`,
      script: 'node_modules/react-scripts/bin/react-scripts.js',
      args: 'start',
      interpreter: `${HOME}/.nvm/versions/node/v18.18.2/bin/node`,
      exec_mode: 'fork',
      env: {
        PORT: '47131',
        HOST: '127.0.0.1',
        BROWSER: 'none',
        REACT_APP_STAGE: 'dev',
        // Served through Apache under dev.img-api.com
        DANGEROUSLY_DISABLE_HOST_CHECK: 'true',
        WDS_SOCKET_PORT: '0',
      },
    },
  ],
};

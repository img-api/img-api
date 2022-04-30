# WELCOME

## CLONE PROJECT

```
git clone git@github.com:sergioamr/img-api.git
```

## INSTALLATION

### Create a virtual environment to run this project

```
cd img-api

# Linux
sudo apt-get install python3-venv    # If needed
python3 -m venv .venv
source .venv/bin/activate

# macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows
py -3 -m venv .venv
.venv\scripts\activate
```

### Install mongodb

The database of choice for this project is Mongodb since we can dynamically grow the project and scale it through clusters

```
sudo apt-get install mongodb-org
```

### Install redis

Our microservices work using redis as our main platform for RPC (Remote Process Procedure)

### Instal imagemagick

```
sudo apt install imagemagick
```

### Update project dependences
```
./update.sh
```

## REFERENCE
https://code.visualstudio.com/docs/python/tutorial-flask
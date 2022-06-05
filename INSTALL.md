# WELCOME

## CLONE PROJECT

```
git clone git@github.com:sergioamr/img-api.git
```

## INSTALLATION

### Create a virtual environment to run this project

You can run the installer, it is what is being used by the CI.
```
./install.sh
```

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
sudo apt-get install mongodb-org -y
```

### Install redis

Our microservices work using redis as our main platform for RPC (Remote Process Procedure)

### Install imagemagick

```
sudo apt install imagemagick -y
```

### Video
sudo apt-get install ffmpeg -y

### Update project dependences
```
./update.sh
```

## REFERENCE
https://code.visualstudio.com/docs/python/tutorial-flask


## Apache Server

``` Bash
sudo apt-get install apache2 -y
sudo apt-get install libapache2-mod-wsgi -y
sudo apt-get remove libapache2-mod-python libapache2-mod-wsgi -y

sudo a2enmod rewrite
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo a2enmod proxy_balancer
sudo a2enmod lbmethod_byrequests
sudo a2enmod wsgi

sudo apt-get install libapache2-mod-wsgi-py3 -y
```
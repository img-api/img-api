#!/bin/bash

cd "${BASH_SOURCE%/*}"

# Check if we should use Docker
USE_DOCKER=false
for arg in "$@"; do
  if [ "$arg" == "--docker" ]; then
    USE_DOCKER=true
  fi
done

if [ "$USE_DOCKER" = true ]; then
  echo "DOCKER MODE: Building and starting Docker container"

  # Check if Docker is installed
  if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh ./get-docker.sh
    rm get-docker.sh
  fi

  # Build Docker image
  echo "Building Docker image..."
  docker build -t img-api:latest -f DockerFile .

  # Start Docker container
  echo "Starting Docker container..."
  docker run -d \
    --name img-api \
    -p 8080:3000 \
    -v "$(pwd):/app" \
    --restart unless-stopped \
    img-api:latest

  echo "Docker container started. Access the application at http://localhost:8080"
  echo "To stop the container: docker stop img-api"
  echo "To view logs: docker logs img-api"

else
  # Regular update process
  if [ ! -d ".venv" ]
  then
     echo "INSTALLING VENV "
     python3 -m venv .venv
  fi

  echo "UPDATING IMG-API"

  . .venv/bin/activate

  git pull --rebase
  pip3 install -r requirements.txt --upgrade

  python -m spacy download en_core_web_sm
fi


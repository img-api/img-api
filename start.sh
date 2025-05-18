#!/bin/bash

# Start cron service
service cron start

# Start MongoDB
echo "Starting MongoDB..."
mkdir -p /data/db
mongod --fork --logpath /var/log/mongodb.log

# Start Redis
echo "Starting Redis..."
redis-server --daemonize yes

# Start Apache if needed
echo "Starting Apache..."
service apache2 start

# Check for environment
if [ -d ".venv" ]; then
  echo "Activating virtual environment..."
  source .venv/bin/activate
fi

# Install requirements if needed
if [ -f "requirements.txt" ]; then
  echo "Installing/updating dependencies..."
  pip install -r requirements.txt
fi

# Start the application
echo "Starting application..."
# You might need to update this command based on how your app should start
# For a Flask app, you would typically use:
# gunicorn -b 0.0.0.0:3000 app:app
python app.py

# Keep container running
tail -f /app/logs/cron.log
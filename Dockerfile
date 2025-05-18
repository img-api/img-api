# Use Python 3.11 as base image
FROM python:3.11

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
    inetutils-ping \
    vim \
    lsof \
    plocate \
    # UI/Display dependencies
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libgtk-3-0 \
    libnss3 \
    libxss1 \
    libxtst6 \
    apache2 \
    libxshmfence1 \
    libglu1-mesa \
    # Other utilities
    telnet \
    cron \
    curl \
    gnupg \
    software-properties-common \
    python3-pip \
    python3-dev \
    python3-wheel \
    python3-venv \
    libxml2-dev \
    libxslt-dev \
    unzip \
    python3-tk \
    libapache2-mod-wsgi-py3 \
    gunicorn \
    imagemagick \
    ffmpeg

# Install MongoDB
#RUN curl -fsSL https://www.mongodb.org/static/pgp/server-4.4.asc | apt-key add - && \
#    echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/4.4 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-4.4.list && \
#    apt-get update && \
#    apt-get install -y mongodb-org

# Install Redis
#RUN apt-get install -y redis-server

# Configure Apache modules
RUN a2enmod rewrite && \
    a2enmod proxy && \
    a2enmod proxy_http && \
    a2enmod proxy_balancer && \
    a2enmod lbmethod_byrequests && \
    a2enmod wsgi

# Create necessary directories
RUN touch /var/log/cron.log

# Set up cron job
RUN echo "*/1 * * * * root /bin/bash -l -c 'echo \"\$(/bin/date) ALIVE\" >> /app/logs/cron.log 2>&1'" > /etc/cron.d/alive
RUN chmod 0744 /etc/cron.d/alive

# Add the default github host to the known_hosts file
RUN ssh-keyscan github.com >> /root/.ssh/known_hosts

# Copy application code
COPY . .

# Make scripts executable
RUN chmod +x start.sh
RUN chmod +x update.sh

# Set up git configuration
RUN git config --global --add safe.directory /app

# Create virtual environment
RUN python3 -m venv .venv
# Install spaCy model
RUN . .venv/bin/activate

# Expose ports - Flask (3000) and debugging (9229)
EXPOSE 3000
EXPOSE 9229

# Also expose MongoDB and Redis ports
#EXPOSE 27017
#EXPOSE 6379
# Expose Apache port
EXPOSE 80

# Set up environment path
ENV PATH="/app/.venv/bin:/app/node_modules/.bin:${PATH}"

# Start the application
CMD ["/bin/bash", "./start.sh"]
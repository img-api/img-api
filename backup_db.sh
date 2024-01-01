#!/bin/bash

# Set the current date as a variable
CURRENT_DATE=$(date +%Y%m%d%H%M%S)

# Directory where you want to store your backups
BACKUP_DIR="/home/imgapi/imgapi_backup"

# Database name to dump
DB_NAME="test"

# Create backup directory if it doesn't exist
mkdir -p $BACKUP_DIR

# Dump the database
mongodump --db $DB_NAME --out $BACKUP_DIR/$DB_NAME-$CURRENT_DATE

# Zip the dump
tar -czvf $BACKUP_DIR/$DB_NAME-$CURRENT_DATE.tar.gz -C $BACKUP_DIR $DB_NAME-$CURRENT_DATE

# Remove the uncompressed dump
rm -rf $BACKUP_DIR/$DB_NAME-$CURRENT_DATE

find $BACKUP_DIR -type f -name "*.gz" -mtime +30 -delete


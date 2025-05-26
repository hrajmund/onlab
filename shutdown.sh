#!/bin/bash

echo "Generating human-readable log from log.json..."

docker exec onlab-controller-1 python cleanup.py

docker cp onlab-controller-1:/app/log_summary.csv ./log_summary.csv

echo "Log summary saved as log_summary.csv =========> SUCCESS"

echo "Shutting down Docker Compose stack..."
docker compose down

echo "Docker compose has been shut down =========> SUCCESS"
exit 0

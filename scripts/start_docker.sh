#!/bin/bash

# Script to start docker compose services in the background

set -e

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "Starting docker compose services in background..."
docker compose up -d --build

echo ""
echo "Services started. Checking status..."
docker compose ps

echo ""
echo "To view logs, run: docker compose logs -f"
echo "To stop services, run: docker compose down"

#!/bin/sh
set -e

# Load environment variables from .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Configuration
URL="http://0.0.0.0:8000"
START_DATE="2026-01-08"
END_DATE="2026-01-15"
SKIP_INGESTION=""
USE_CLASSIFIER="True"
TOP_K=5
CATEGORY=""
TIMEOUT=600

# Build arguments
ARGS="--url ${URL} --top-k ${TOP_K} --timeout ${TIMEOUT}"

if [ -n "${START_DATE}" ]; then
    ARGS="${ARGS} --start-date ${START_DATE}"
fi

if [ -n "${END_DATE}" ]; then
    ARGS="${ARGS} --end-date ${END_DATE}"
fi

if [ -n "${SKIP_INGESTION}" ]; then
    ARGS="${ARGS} --skip-ingestion"
fi

if [ -n "${USE_CLASSIFIER}" ]; then
    ARGS="${ARGS} --use-classifier ${USE_CLASSIFIER}"
fi

if [ -n "${CATEGORY}" ]; then
    ARGS="${ARGS} --category ${CATEGORY}"
fi

echo "ARGS: ${ARGS}"

python src/callers/call_workflow_endpoint.py ${ARGS}

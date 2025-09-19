#!/bin/sh
set -x

# Load environment variables from .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

PROM_PATH="/tmp/prometheus_dir"
mkdir -p ${PROM_PATH}
echo "Create ${PROM_PATH} for prometheus"
echo "ENV_FILE_PATH: '${ENV_FILE_PATH}'"

export prometheus_multiproc_dir=${PROM_PATH}
export PROMETHEUS_MULTIPROC_DIR=${PROM_PATH}

# Start the Gunicorn server in the background
gunicorn "src.app:create_app()" \
    -k uvicorn.workers.UvicornWorker \
    -w 1 \
    -t 20000 \
    --bind 0.0.0.0:8000 \
    --reload

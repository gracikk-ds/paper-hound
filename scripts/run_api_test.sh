#!/bin/sh
set -x

export http_proxy="http://proxy.sberdevices.ru:3128"
export https_proxy="http://proxy.sberdevices.ru:3128"
export no_proxy="localhost,127.0.0.1,sberdevices.ru,docker:2375,docker:2376"
export HTTP_PROXY="http://proxy.sberdevices.ru:3128"
export HTTPS_PROXY="http://proxy.sberdevices.ru:3128"
export NO_PROXY="localhost,127.0.0.1,sberdevices.ru,docker:2375,docker:2376"

cd /workspace/
gunicorn "src.app:create_app()" -k uvicorn.workers.UvicornWorker -w 1 -t 20000 --bind 0.0.0.0:8001 --reload &

# Wait for the server to start
until curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/health/health_checker | grep -q "200"; do
  echo "Waiting for the server to start..."
  sleep 7
done
echo "Server is up and running!"

pytest -s tests

pkill -f "gunicorn"

#!/bin/bash
# AgentOS — Production launcher with multi-worker support
set -e

cd "$(dirname "$0")"
source .venv/bin/activate

# Production settings
WORKERS=${WORKERS:-1}
HOST=${HOST:-0.0.0.0}
PORT=${PORT:-8000}

echo "AgentOS Production Mode"
echo "  Workers: $WORKERS"
echo "  Port:    $PORT"

if [ "$WORKERS" -gt 1 ]; then
    # Multi-worker with gunicorn (horizontal scaling)
    pip install gunicorn -q 2>/dev/null
    exec gunicorn backend.main:app \
        -w "$WORKERS" \
        -k uvicorn.workers.UvicornWorker \
        --bind "$HOST:$PORT" \
        --timeout 120 \
        --access-logfile - \
        --error-logfile -
else
    # Single worker with uvicorn
    exec python3 -m uvicorn backend.main:app \
        --host "$HOST" \
        --port "$PORT"
fi

#!/bin/bash
set -e

echo "[entrypoint] Starting Flask App (Background)..."
cd /app
# Ensure python path includes /app so backend package is found
export PYTHONPATH=/app
# Run Flask on port 5000 (localhost by default in app.py, but need to ensure it's accessible to Nginx)
# app.py has app.run(host="0.0.0.0", port=5000)
python -u -m backend.api.app &
FLASK_PID=$!

echo "[entrypoint] Starting Nginx (Foreground)..."
# Use exec to replace shell with Nginx, but we want to monitor Flask?
# Simple approach: run Nginx in foreground
nginx -g "daemon off;"

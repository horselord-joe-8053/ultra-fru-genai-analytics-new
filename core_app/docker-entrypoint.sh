#!/bin/bash
set -e

# Cloud Run sets PORT=8080; use it for Nginx. Default 5001 for local/ECS.
export PORT="${PORT:-5001}"
sed -i "s/listen 5001/listen ${PORT}/" /etc/nginx/nginx.conf
echo "[entrypoint] Nginx will listen on port ${PORT}"

echo "[entrypoint] Starting Flask App (Background)..."
cd /app
# Ensure python path includes /app so backend package is found
export PYTHONPATH=/app
# Flask must listen on 5000 (Nginx proxies to 127.0.0.1:5000). Cloud Run sets PORT=8080 for Nginx.
# Override PORT for Flask so app.py binds to 5000; Nginx uses PORT for external traffic.
PORT=5000 python -u -m backend.api.app &
FLASK_PID=$!

echo "[entrypoint] Starting Nginx (Foreground)..."
# Use exec to replace shell with Nginx, but we want to monitor Flask?
# Simple approach: run Nginx in foreground
nginx -g "daemon off;"

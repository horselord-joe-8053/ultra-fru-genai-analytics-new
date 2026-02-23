# Stage 1: Build Frontend
FROM node:20 AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
# Use npm install and avoid any potential issues with old package-lock.json
RUN npm install && npm install vite
COPY frontend/ .
# Build the React app
RUN ./node_modules/.bin/vite build

# Stage 2: Runtime (Python + Nginx)
FROM python:3.11-slim
# Content-based build skip: hash of build context, passed as --build-arg by build_and_push_images.py.
# Stored in image for traceability; deploy uses S3-stored hash to skip build when unchanged.
ARG BUILD_CONTEXT_HASH
LABEL build_context_hash=${BUILD_CONTEXT_HASH}

# Install Nginx and runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Backend Code
COPY backend /app/backend

# Copy Frontend Build Artifacts
# Nginx config expects static files at /usr/share/nginx/html
COPY --from=frontend-builder /app/frontend/dist /usr/share/nginx/html

# Copy Nginx Config
COPY nginx.conf /etc/nginx/nginx.conf

# Copy Entrypoint
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Expose port (Nginx listens on 5001 as per config)
EXPOSE 5001

ENTRYPOINT ["/app/docker-entrypoint.sh"]

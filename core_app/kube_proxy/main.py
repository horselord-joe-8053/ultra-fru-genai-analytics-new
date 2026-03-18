"""
GCP Kube proxy: single entry point for frontend (GCS) + API (GKE LB).

Cloud Run gives HTTPS + *.run.app domain. This proxy routes:
- /, /index.html, /assets/*, etc. -> fetch from GCS bucket
- /query, /analytics, /rawdata, /health, /version -> proxy to GKE LoadBalancer

Env vars: GKE_LB_URL, GCS_BUCKET, GCP_PROJECT, PORT
"""
import os
import io
import requests
from flask import Flask, request, Response, stream_with_context
from google.cloud import storage

app = Flask(__name__)

# API paths that go to GKE LB (must match cloud_cdn path rules)
API_PREFIXES = ("/query", "/analytics", "/rawdata", "/health", "/version")
_raw = os.environ.get("GKE_LB_URL", "").strip().rstrip("/")
GKE_LB_URL = _raw if _raw.startswith("http") else f"http://{_raw}" if _raw else ""
GCS_BUCKET = os.environ.get("GCS_BUCKET", "")
GCP_PROJECT = os.environ.get("GCP_PROJECT", "")


def _is_api_path(path: str) -> bool:
    """True if path should be proxied to GKE (not served from GCS)."""
    if path == "/" or not path:
        return False
    return any(path == p or path.startswith(p + "/") for p in API_PREFIXES)


def _fetch_from_gcs(path: str) -> tuple[bytes, str, int]:
    """Fetch object from GCS. Returns (body, content_type, status_code)."""
    if not GCS_BUCKET or not GCP_PROJECT:
        return b"GCS not configured", "text/plain", 503
    path = path.lstrip("/") or "index.html"
    # Normalize: /assets/foo -> assets/foo
    if path.startswith("assets/"):
        pass
    elif path in ("", "index.html"):
        path = "index.html"
    try:
        client = storage.Client(project=GCP_PROJECT)
        bucket = client.bucket(GCS_BUCKET)
        blob = bucket.blob(path)
        data = blob.download_as_bytes()
        content_type = blob.content_type or "application/octet-stream"
        return data, content_type, 200
    except Exception as e:
        app.logger.warning(f"GCS fetch failed for {path}: {e}")
        return b"Not found", "text/plain", 404


def _proxy_to_gke(path: str, method: str, headers: dict, data) -> Response:
    """Proxy request to GKE LB."""
    if not GKE_LB_URL:
        return Response("GKE LB not configured", status=503)
    url = f"{GKE_LB_URL}{path}"
    if request.query_string:
        url += "?" + request.query_string.decode()
    # Forward relevant headers, drop hop-by-hop
    forward_headers = {
        k: v for k, v in request.headers if k.lower() not in (
            "host", "connection", "transfer-encoding", "content-length"
        )
    }
    try:
        resp = requests.request(
            method, url, headers=forward_headers, data=data,
            timeout=60, stream=True, allow_redirects=False,
        )
        def gen():
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
        return Response(
            stream_with_context(gen()),
            status=resp.status_code,
            headers={k: v for k, v in resp.headers.items() if k.lower() not in ("transfer-encoding",)},
        )
    except Exception as e:
        app.logger.warning(f"GKE proxy failed for {path}: {e}")
        return Response(str(e), status=502)


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def proxy(path: str):
    full_path = "/" + path if path else "/"
    if _is_api_path(full_path):
        return _proxy_to_gke(
            full_path, request.method,
            dict(request.headers), request.get_data(),
        )
    body, content_type, status = _fetch_from_gcs(full_path)
    return Response(body, status=status, mimetype=content_type)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

"""nginx must proxy API routes used by Vite dev server — not fall through to SPA index.html."""

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_NGINX_CONF = _REPO_ROOT / "core_app" / "nginx.conf"

# Keep in sync with core_app/frontend/vite.config.ts server.proxy paths.
_REQUIRED_API_PREFIXES = (
    "query",
    "analytics",
    "health",
    "version",
    "rawdata",
    "model-catalog",
)


def test_nginx_conf_proxies_api_routes_including_model_catalog():
    text = _NGINX_CONF.read_text(encoding="utf-8")
    for prefix in _REQUIRED_API_PREFIXES:
        assert prefix in text, f"nginx.conf must proxy /{prefix} to Flask"

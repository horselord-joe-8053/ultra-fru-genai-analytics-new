"""
Shared verification config: timeouts and constants.

Used by verify_api_endpoints. Override via .env:
  VERIFY_TIMEOUT_SEC, VERIFY_HEARTBEAT_INTERVAL_SEC,
  VERIFY_QUERY_STREAM_TIMEOUT_PER_REQUEST_SEC
"""
from tools.cloud_shared.env import get_int_env

# CloudFront/LB propagation can take 5–15 min
VERIFY_TIMEOUT_SEC = get_int_env("VERIFY_TIMEOUT_SEC", 900)
VERIFY_HEARTBEAT_INTERVAL_SEC = get_int_env("VERIFY_HEARTBEAT_INTERVAL_SEC", 30)
# QueryStream: LLM streaming can take 60–120+ s; 3 min default
QUERY_STREAM_TIMEOUT_PER_REQUEST_SEC = get_int_env("VERIFY_QUERY_STREAM_TIMEOUT_PER_REQUEST_SEC", 180)

# 502/503 = transient; 403 = real failure (not retriable)
VERIFY_RETRIABLE_HTTP_CODES = frozenset({502, 503})

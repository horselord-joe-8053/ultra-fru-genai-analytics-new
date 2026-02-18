
import os
from pathlib import Path

def load_dotenv(path: str = ".env", override: bool = False):
    """
    Load .env into os.environ.
    When override=False (default), do not overwrite existing env vars.
    This allows callers (e.g. deploy) to set values that child scripts (e.g. build) will keep.
    When override=True, always overwrite (legacy behavior).
    """
    # Fallback to env.fru if default .env is missing and env.fru exists
    if path == ".env" and not Path(".env").exists() and Path("env.fru").exists():
        path = "env.fru"
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        key = k.strip()
        if override or key not in os.environ:
            os.environ[key] = v.strip()

def require(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise SystemExit(f"Missing required env var: {name}")
    return v

def get_int_env(name: str, default: int) -> int:
    v = os.getenv(name)
    if not v:
        return default
    try:
        return int(v)
    except ValueError:
        return default

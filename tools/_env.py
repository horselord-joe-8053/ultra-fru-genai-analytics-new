
import os
from pathlib import Path

def load_dotenv(path: str = ".env"):
    # Fallback to env.fru if default .env is missing or inaccessible
    if path == ".env" and Path("env.fru").exists():
        path = "env.fru"
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

def require(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise SystemExit(f"Missing required env var: {name}")
    return v

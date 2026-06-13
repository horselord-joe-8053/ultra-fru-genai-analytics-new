
import os
from pathlib import Path

__all__ = [
    "load_dotenv",
    "require",
    "get_int_env",
    "EnvVarNotFound",
    "validate_active_embedding_profile_env",
]


class EnvVarNotFound(Exception):
    """Raised when a required env var is missing."""

    def __init__(self, name: str, hint: str = ""):
        self.name = name
        self.hint = hint
        msg = f"Required env var '{name}' is not set."
        if hint:
            msg += f" {hint}"
        super().__init__(msg)


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
        raise EnvVarNotFound(name)
    return v

def get_int_env(name: str, default: int) -> int:
    v = os.getenv(name)
    if not v:
        return default
    try:
        return int(v)
    except ValueError:
        return default


def validate_active_embedding_profile_env() -> None:
    """
    Ensure credentials exist for the active EMBEDDING_ACTIVE_PROFILE.

    Raises EnvVarNotFound when provider is modelark (ARK_*) or openai (OPENAI_API_KEY).
    No-op when profile config cannot be loaded (e.g. tools-only context without backend).
    """
    try:
        from backend.env_utils.cloud_shared.embedding_profiles import get_active_profile

        profile = get_active_profile()
    except Exception:
        return

    if profile.provider == "modelark":
        require("ARK_API_KEY")
        require(profile.model_env)
    elif profile.provider == "openai":
        require("OPENAI_API_KEY")

#!/usr/bin/env python3
"""Verify EMBEDDING_ACTIVE_PROFILE resolves and matches pgvector column naming."""
import sys

from tools.cloud_shared.env import load_dotenv, validate_active_embedding_profile_env

load_dotenv()


def main() -> int:
    from backend.env_utils.cloud_shared.embedding_profiles import (
        get_active_profile,
        get_active_pgvector_column,
    )

    profile = get_active_profile()
    col = get_active_pgvector_column()
    print(f"profile={profile.name} provider={profile.provider} dimension={profile.dimension}")
    print(f"pgvector_column={col}")
    if col != profile.expected_column_name():
        print("ERROR: column name mismatch", file=sys.stderr)
        return 1
    try:
        validate_active_embedding_profile_env()
        print("credentials=ok")
    except Exception as e:
        print(f"WARN: credentials check failed: {e}", file=sys.stderr)
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Verify EMBEDDING_ACTIVE_PROFILE (search lane) and embedding column population."""
import os
import sys

from tools.cloud_shared.env import load_dotenv, validate_active_embedding_profile_env

load_dotenv()


def main() -> int:
    from backend.env_utils.cloud_shared.embedding_profiles import (
        get_active_profile,
        get_active_pgvector_column,
        get_profiles,
    )

    profile = get_active_profile()
    col = get_active_pgvector_column()
    print(f"search_profile={profile.name} provider={profile.provider} dimension={profile.dimension}")
    print(f"search_pgvector_column={col}")
    if col != profile.expected_column_name():
        print("ERROR: column name mismatch", file=sys.stderr)
        return 1
    try:
        validate_active_embedding_profile_env()
        print("search_lane_credentials=ok")
    except Exception as e:
        print(f"WARN: search lane credentials check failed: {e}", file=sys.stderr)

    if os.environ.get("PGHOST"):
        import psycopg2

        conn = psycopg2.connect(
            host=os.environ["PGHOST"],
            port=int(os.environ.get("PGPORT", "5432")),
            user=os.environ.get("PGUSER", "postgres"),
            password=os.environ["PGPASSWORD"],
            dbname=os.environ.get("PGDATABASE", "fru_db"),
        )
        try:
            from backend.services.embedding_sync import embedding_column_population_counts

            counts = embedding_column_population_counts(conn)
            print(f"column_population={counts}")
            total = counts.get("total_rows", 0)
            for name in get_profiles():
                if name in counts and total and counts[name] < total:
                    print(f"WARN: profile {name} has {counts[name]}/{total} rows populated", file=sys.stderr)
        finally:
            conn.close()

    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

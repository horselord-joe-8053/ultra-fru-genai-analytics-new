#!/usr/bin/env python3
"""
DEPRECATED: use load_openai_embeddings_to_pgvector.py (--sync-embeddings) or db_setup/load.py.

Scalar CSV load + dual-profile embedding_sync.
"""
import sys

from backend.etl.load_openai_embeddings_to_pgvector import main

if __name__ == "__main__":
    if "--sync-embeddings" not in sys.argv:
        sys.argv.append("--sync-embeddings")
    main()

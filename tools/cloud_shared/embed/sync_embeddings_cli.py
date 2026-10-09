#!/usr/bin/env python3
"""
Thin CLI wrapper for backend.services.embedding_sync.

  PYTHONPATH=core_app python tools/cloud_shared/embed/sync_embeddings_cli.py --all --missing-only
"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "core_app"))

from backend.services.embedding_sync import main

if __name__ == "__main__":
    raise SystemExit(main())

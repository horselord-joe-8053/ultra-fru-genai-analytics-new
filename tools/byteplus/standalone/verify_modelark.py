#!/usr/bin/env python3
"""Smoke-test ModelArk chat + embeddings when ARK_* env vars are set."""
import os
import sys

from tools.cloud_shared.env import load_dotenv

load_dotenv()


def main() -> int:
    if not os.environ.get("ARK_API_KEY", "").strip():
        print("SKIP: ARK_API_KEY not set")
        return 0

    from backend.env_utils.byteplus.modelark_client import ModelArkClient
    from backend.env_utils.cloud_shared.embedding_profiles import get_profiles
    from backend.env_utils.byteplus.embeddings import ModelArkEmbeddingClient

    chat_id = os.environ.get("ARK_CHAT_MODEL_ID", "").strip()
    if chat_id:
        client = ModelArkClient()
        out = client.complete("You are terse.", "Reply with exactly: pong")
        print(f"chat: {out['text'][:80]!r}")

    embed_id = os.environ.get("ARK_EMBEDDING_MODEL_ID", "").strip()
    if embed_id:
        prof = get_profiles()["skylark_2048"]
        emb = ModelArkEmbeddingClient(prof)
        vec = emb.embed_texts(["smoke test"])[0]
        print(f"embed: dim={len(vec)}")
    else:
        print("SKIP: ARK_EMBEDDING_MODEL_ID not set")

    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
Smoke-test each ModelArk chat profile id from model_profiles.yaml.

Requires ARK_API_KEY in .env.
"""
from __future__ import annotations

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
    from backend.env_utils.cloud_shared.model_profiles import (
        get_chat_profiles_dict,
        resolve_chat_model_id,
    )

    modelark_chats = {
        name: prof
        for name, prof in get_chat_profiles_dict().items()
        if prof.inference == "modelark"
    }
    client = ModelArkClient()
    failures = 0
    for name, prof in modelark_chats.items():
        model_id = resolve_chat_model_id(name)
        try:
            out = client.complete("You are terse.", "Reply with exactly: pong", model_id=model_id)
            print(f"chat {name} ({model_id}): {out['text'][:40]!r}")
        except Exception as exc:
            failures += 1
            print(f"FAIL chat {name} ({model_id}): {exc}")

    embed_id = os.environ.get("ARK_EMBEDDING_MODEL_ID", "").strip()
    if embed_id:
        prof = get_profiles()["skylark_2048"]
        emb = ModelArkEmbeddingClient(prof)
        vec = emb.embed_texts(["smoke test"])[0]
        print(f"embed: dim={len(vec)}")
    else:
        print("SKIP: ARK_EMBEDDING_MODEL_ID not set")

    if failures:
        print(f"FAILED: {failures} chat profile(s)")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

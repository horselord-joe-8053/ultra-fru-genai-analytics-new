"""
Smoke-test enabled chat profiles for the current CLOUD_PROVIDER.

Used by local/AWS/GCP verify scripts; skips profiles without credentials.
"""
from __future__ import annotations

import os
import sys

from tools.cloud_shared.verify.verify_summary import VerifyRow


def verify_chat_profiles() -> tuple[bool, list[VerifyRow]]:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    core_app = os.path.join(repo_root, "core_app")
    if core_app not in sys.path:
        sys.path.insert(0, core_app)

    from backend.env_utils.cloud_shared.client_factory import create_llm_client_for_choice
    from backend.env_utils.cloud_shared.model_profiles import (
        chat_choice_enabled,
        get_chat_profiles_dict,
        resolve_chat_model_id,
    )
    from backend.env_utils.cloud_shared.provider import get_cloud_provider

    cloud = get_cloud_provider()
    rows: list[VerifyRow] = []
    ok = True
    for name in get_chat_profiles_dict():
        if not chat_choice_enabled(name):
            rows.append(
                VerifyRow(
                    provider=cloud,
                    scope="shared",
                    endpoint=f"chat:{name}",
                    ok=True,
                    notes="skipped (no creds)",
                )
            )
            continue
        try:
            client = create_llm_client_for_choice(name)
            model_id = resolve_chat_model_id(name, cloud)
            result = client.complete(
                "You are terse.", "Reply pong", model_id=model_id, max_tokens=32
            )
            text = (result.get("text") or "")[:40]
            rows.append(
                VerifyRow(
                    provider=cloud,
                    scope="shared",
                    endpoint=f"chat:{name}",
                    ok=True,
                    notes=f"{type(client).__name__} {model_id} → {text!r}",
                )
            )
        except Exception as exc:
            ok = False
            rows.append(
                VerifyRow(
                    provider=cloud,
                    scope="shared",
                    endpoint=f"chat:{name}",
                    ok=False,
                    notes=str(exc)[:200],
                )
            )
    return ok, rows

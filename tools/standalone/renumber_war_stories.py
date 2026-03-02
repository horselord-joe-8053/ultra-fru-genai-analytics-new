#!/usr/bin/env python3
"""
Renumber war stories in each file to have independent 1, 2, 3...
Also updates subsection numbers (e.g. ### 2.1 -> ### 1.1).
Run from project root.
"""
import re
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WAR_DIR = os.path.join(REPO_ROOT, "war_stories")


def renumber_file(path: str):
    """Renumber ## N. and ### N.x to sequential 1, 2, 3... Process each story block."""
    with open(path, "r") as f:
        content = f.read()

    # Split by ## and process each story block. Keep header (before first ##).
    parts = re.split(r"(?=^## \d+\. )", content, flags=re.MULTILINE)
    header = parts[0] if parts else ""
    story_blocks = parts[1:] if len(parts) > 1 else []

    result = [header]
    for i, block in enumerate(story_blocks):
        new_id = i + 1
        # Replace ## N. with ## new_id.
        block = re.sub(r"^## \d+\. ", f"## {new_id}. ", block, count=1, flags=re.MULTILINE)
        # Replace ### N.x with ### new_id.x (N = old story id in this block)
        block = re.sub(r"^### \d+\.(\d+)\s*", f"### {new_id}.\\1 ", block, flags=re.MULTILINE)
        result.append(block)

    content = "".join(result)
    # Collapse multiple ---\n\n--- into single ---
    content = re.sub(r"(\n---\n\n)(\s*---\n\n)+", r"\1", content)

    with open(path, "w") as f:
        f.write(content)
    print(f"Renumbered {path}")


def main():
    renumber_file(os.path.join(WAR_DIR, "WAR_STORIES_AWS.md"))
    renumber_file(os.path.join(WAR_DIR, "WAR_STORIES_GCP.md"))
    renumber_file(os.path.join(WAR_DIR, "WAR_STORIES_CLOUD_SHARED.md"))


if __name__ == "__main__":
    main()

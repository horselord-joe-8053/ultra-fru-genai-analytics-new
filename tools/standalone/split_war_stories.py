#!/usr/bin/env python3
"""
One-off: Split README_WAR_STORIES.md into AWS, GCP, and CLOUD_SHARED.
Run from project root.
"""
import re
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Stories that are AWS-specific (EKS, ECR, CloudFront, S3, RDS, Aurora, Bedrock, ELB, NLB, VPC, etc.)
AWS_IDS = {
    2, 3, 4, 5, 6, 7, 12, 13, 15, 16, 19, 21, 22, 23, 24, 25, 26, 27, 28,
    33, 38, 41, 42, 43, 44, 45, 46, 48, 49, 50, 52, 55, 56, 58, 59, 63, 64, 65, 66, 67, 68,
}

# Stories that are GCP-specific
GCP_IDS = {70, 71}


def parse_stories(content: str) -> list[tuple[int, str]]:
    """Return list of (story_id, story_text) including the --- separator before each."""
    pattern = re.compile(r'^## (\d+)\. ', re.MULTILINE)
    matches = list(pattern.finditer(content))
    stories = []
    for i, m in enumerate(matches):
        sid = int(m.group(1))
        start = m.start()
        end = matches[i + 1].start() - 1 if i + 1 < len(matches) else len(content)
        # Include the ---\n\n before ## N.
        pre_start = content.rfind("\n---\n\n", 0, start)
        if pre_start >= 0:
            start = pre_start + 1  # after \n, so we include ---\n\n
        stories.append((sid, content[start:end].rstrip()))
    return stories


def main():
    src = os.path.join(REPO_ROOT, "README_WAR_STORIES.md")
    war_dir = os.path.join(REPO_ROOT, "docs", "war_stories")
    os.makedirs(war_dir, exist_ok=True)

    with open(src, "r") as f:
        content = f.read()

    stories = parse_stories(content)
    header = "# README_WAR_STORIES\n\nA curated list of **non-trivial technical war stories**, capturing real lessons suitable for **senior-level interviews**.\n\n"

    aws_parts = [header.replace("README_WAR_STORIES", "WAR_STORIES_AWS")]
    aws_parts.append("# AWS-Specific War Stories\n\n")
    gcp_parts = [header.replace("README_WAR_STORIES", "WAR_STORIES_GCP")]
    gcp_parts.append("# GCP-Specific War Stories\n\n")
    shared_parts = [header.replace("README_WAR_STORIES", "WAR_STORIES_CLOUD_SHARED")]
    shared_parts.append("# Cloud-Agnostic / Multi-Cloud War Stories\n\n")

    for sid, text in stories:
        if sid in AWS_IDS:
            aws_parts.append(text)
            aws_parts.append("\n\n---\n\n")
        elif sid in GCP_IDS:
            gcp_parts.append(text)
            gcp_parts.append("\n\n---\n\n")
        else:
            shared_parts.append(text)
            shared_parts.append("\n\n---\n\n")

    def write_file(name: str, parts: list):
        p = os.path.join(war_dir, name)
        with open(p, "w") as f:
            f.write("".join(parts).rstrip())
            f.write("\n")
        print(f"Wrote {p}")

    # Step 1: Move README to docs/war_stories/WAR_STORIES.md
    dest = os.path.join(war_dir, "WAR_STORIES.md")
    with open(dest, "w") as f:
        f.write(content)
    os.remove(src)
    print(f"Moved {src} -> {dest}")

    # Step 2: Extract AWS
    write_file("WAR_STORIES_AWS.md", aws_parts)
    # Step 3: Create GCP
    write_file("WAR_STORIES_GCP.md", gcp_parts)
    # Step 4: Overwrite WAR_STORIES.md with shared content, rename to WAR_STORIES_CLOUD_SHARED.md
    write_file("WAR_STORIES.md", shared_parts)
    os.rename(dest, os.path.join(war_dir, "WAR_STORIES_CLOUD_SHARED.md"))
    print(f"Renamed WAR_STORIES.md -> WAR_STORIES_CLOUD_SHARED.md")


if __name__ == "__main__":
    main()

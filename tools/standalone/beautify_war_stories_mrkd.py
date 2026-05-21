#!/usr/bin/env python3
"""Apply mrkd-markdown-authoring structure to WAR_STORIES_*.md collection files."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

H1_STYLE = (
    'style="color:#0d47a1;font-size:1.5em;font-weight:700;'
    'border-bottom:2px solid #90caf9;padding-bottom:0.25em;margin-top:0"'
)
H2_STYLE = (
    'style="color:#1565c0;font-size:1.22em;font-weight:650;'
    'border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em"'
)
H2_STORY_STYLE = (
    'style="color:#1565c0;margin-top:1.35em;margin-bottom:0.5em;font-weight:650;'
    'border-left:4px solid #42a5f5;padding-left:10px"'
)
H3_STYLE = (
    'style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600"'
)

MERMAID_INIT = (
    "%%{init: {'theme': 'base', 'themeVariables': { 'fontSize': '11px', "
    "'fontFamily': 'sans-serif' }, 'flowchart': { 'padding': 8, 'nodeSpacing': 25, "
    "'rankSpacing': 30 }}}%%"
)

READING_GUIDE_TABLE = """<table>
<thead>
<tr style="background:#1565c0;color:white"><th style="padding:8px">Field / label</th><th style="padding:8px">Meaning</th></tr>
</thead>
<tbody>
<tr><td style="background:#e3f2fd;padding:8px"><strong>creation</strong> / <strong>last_updated</strong></td><td style="background:#e8f5e9;padding:8px">When the story was first captured and last revised (<code>&lt;YYMMDD&gt;</code> or <code>&lt;YYMMDD-HHMMSS&gt;</code>).</td></tr>
<tr><td style="background:#e3f2fd;padding:8px"><strong>keywords</strong></td><td style="background:#e8f5e9;padding:8px">Grep-friendly index into problem area and stack.</td></tr>
<tr><td style="background:#e3f2fd;padding:8px"><strong>difficulty</strong> / <strong>significance</strong></td><td style="background:#e8f5e9;padding:8px">Relative depth (1–10) and how reusable the lesson is for interviews.</td></tr>
<tr><td style="background:#e3f2fd;padding:8px"><strong>N.1–N.5</strong></td><td style="background:#e8f5e9;padding:8px">Context → Root Cause → Key Insight → Resolution → Takeaway.</td></tr>
</tbody>
</table>"""

SUBTITLE_BY_FILE = {
    "WAR_STORIES_AWS.md": "AWS-Specific War Stories",
    "WAR_STORIES_CLOUD_SHARED.md": "Cloud-Agnostic / Multi-Cloud War Stories",
    "WAR_STORIES_GCP.md": "GCP-Specific War Stories",
    "WAR_STORIES_OTHER.md": None,
}

STORY_H2_RE = re.compile(r"^## (\d+)\. (.+)$")
SUBSECTION_H3_RE = re.compile(r"^### (\d+)\.(\d+) (.+)$")
TITLE_H1_RE = re.compile(r"^# (WAR_STORIES_\w+)$")
SUBTITLE_H1_RE = re.compile(r"^# (.+)$")

FENCE_OPEN_RE = re.compile(r"^```(\w*)$")


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _inline_md_to_html(cell: str) -> str:
    cell = cell.strip()
    cell = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", cell)
    cell = re.sub(r"`([^`]+)`", r"<code>\1</code>", cell)
    return cell


def _guess_fence_lang(body: str) -> str:
    lines = [ln for ln in body.splitlines() if ln.strip()]
    if not lines:
        return "text"
    first = lines[0].strip()
    if first.startswith(("graph ", "flowchart ", "sequenceDiagram", "classDiagram")):
        return "mermaid"
    if first.startswith(("{", "[")) or re.match(r'^\s*"[^{]', first):
        return "json"
    if first.startswith(("import ", "from ", "def ", "class ", "with open")):
        return "python"
    if first.startswith(("#!", "# ", "if ", "export ", "invalidation_id=", "curl ", "aws ")):
        return "bash"
    if first.startswith(("apiVersion:", "kind:", "---")):
        return "yaml"
    if "=" in first and ("=" in first or first.startswith("PG")):
        return "text"
    return "text"


def _parse_md_table_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def _is_separator_row(cells: list[str]) -> bool:
    return all(re.match(r"^:?-+:?$", c.replace(" ", "")) for c in cells if c)


def _md_table_to_html(lines: list[str]) -> str:
    rows = [_parse_md_table_row(ln) for ln in lines]
    if len(rows) < 2:
        return "\n".join(lines)
    header = rows[0]
    body_rows = rows[2:] if len(rows) > 1 and _is_separator_row(rows[1]) else rows[1:]
    parts = [
        "<table>",
        "<thead>",
        '<tr style="background:#1565c0;color:white">',
    ]
    for h in header:
        parts.append(f'<th style="padding:8px">{_inline_md_to_html(h)}</th>')
    parts.extend(["</tr>", "</thead>", "<tbody>"])
    alt = ("#e8f5e9", "#fff3e0")
    for i, row in enumerate(body_rows):
        bg = alt[i % 2]
        parts.append("<tr>")
        for j, cell in enumerate(row):
            if j == 0:
                parts.append(
                    f'<td style="background:#e3f2fd;padding:8px">{_inline_md_to_html(cell)}</td>'
                )
            else:
                parts.append(f'<td style="padding:8px;background:{bg}">{_inline_md_to_html(cell)}</td>')
        parts.append("</tr>")
    parts.extend(["</tbody>", "</table>"])
    return "\n".join(parts)


def _fix_mermaid_block(content: str) -> str:
    lines = content.splitlines()
    if not lines or not lines[0].strip().startswith("%%{init:"):
        lines.insert(0, MERMAID_INIT)
    out: list[str] = []
    for ln in lines:
        if ln.strip().startswith("style ") and "font-size" not in ln:
            ln = ln.rstrip()
            if ln.endswith("}"):
                ln = ln[:-1] + ",font-size:9px}"
            else:
                ln = ln + ",font-size:9px"
        out.append(ln)
    return "\n".join(out)


def _tag_untagged_fences(text: str) -> str:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    while i < len(lines):
        m = FENCE_OPEN_RE.match(lines[i].rstrip("\n"))
        if not m:
            out.append(lines[i])
            i += 1
            continue
        lang = m.group(1)
        i += 1
        body_lines: list[str] = []
        while i < len(lines) and lines[i].rstrip("\n") != "```":
            body_lines.append(lines[i])
            i += 1
        body = "".join(body_lines)
        if not lang:
            lang = _guess_fence_lang(body)
        if lang == "mermaid":
            fixed = _fix_mermaid_block(body.rstrip("\n"))
            body_lines = [ln + "\n" for ln in fixed.splitlines()]
        out.append(f"```{lang}\n")
        out.extend(body_lines)
        if i < len(lines):
            out.append(lines[i])
            i += 1
    return "".join(out)


def _convert_md_tables(text: str) -> str:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|"):
            block: list[str] = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                block.append(lines[i].rstrip("\n"))
                i += 1
            out.append(_md_table_to_html(block) + "\n")
            continue
        out.append(lines[i])
        i += 1
    return "".join(out)


def _short_gist(title: str, max_words: int = 10) -> str:
    words = title.split()
    if len(words) <= max_words:
        return title
    return " ".join(words[:max_words]) + "…"


def _build_front_matter(
    file_name: str,
    title: str,
    intro: str,
    stories: list[tuple[int, str]],
) -> str:
    slug = (
        file_name.replace(".md", "")
        .lower()
        .removeprefix("war_stories_")
        .replace("_", "-")
    )
    title_id = f"war-stories-{slug}-title"
    subtitle = SUBTITLE_BY_FILE.get(file_name)
    parts = [
        f'<h1 id="{title_id}" {H1_STYLE}>{title}</h1>\n',
        "\n",
        intro + "\n",
        "\n",
        "**Authoring discipline:** `.cursor/rules/exwar-war-stories-extraction.mdc` "
        "and `.cursor/rules/mrkd-markdown-authoring.mdc`.\n\n",
    ]
    if subtitle:
        parts.append(f"**{subtitle}**\n\n")
    parts.extend(
        [
            "---\n\n",
            f'<h2 id="document-outline" {H2_STYLE}>Document outline</h2>\n\n',
            "1. [Reading guide](#reading-guide) — metadata and subsection labels.\n",
            "2. [Story index](#story-index) — numbered links and gists for every story.\n",
            "\n---\n\n",
        ]
    )
    parts.append(f'<h2 id="reading-guide" {H2_STYLE}>Reading guide</h2>\n\n')
    parts.append(READING_GUIDE_TABLE + "\n\n---\n\n")
    parts.append(f'<h2 id="story-index" {H2_STYLE}>Story index</h2>\n\n')
    parts.append("<table>\n<thead>\n")
    parts.append(
        '<tr style="background:#1565c0;color:white">'
        '<th style="padding:8px">#</th>'
        '<th style="padding:8px">Title</th>'
        '<th style="padding:8px">Gist</th></tr>\n</thead>\n<tbody>\n'
    )
    alt = ("#fff3e0", "#e8f5e9")
    for i, (num, story_title) in enumerate(stories):
        bg = alt[i % 2]
        gist = _short_gist(story_title, 12)
        parts.append(
            f'<tr><td style="background:#e3f2fd;padding:8px;text-align:right">{num}</td>'
            f'<td style="padding:8px;background:{bg}">'
            f'<a href="#war-story-{num}">{num}. {_escape_html(story_title)}</a></td>'
            f'<td style="padding:8px;background:{bg}">{_escape_html(gist)}</td></tr>\n'
        )
    parts.append("</tbody>\n</table>\n\n---\n\n")
    return "".join(parts)


def beautify(text: str, file_name: str) -> str:
    if '<h1 id="war-stories-' in text and '<h2 id="war-story-' in text:
        return text
    lines = text.splitlines()
    stories: list[tuple[int, str]] = []
    for ln in lines:
        m = STORY_H2_RE.match(ln)
        if m:
            stories.append((int(m.group(1)), m.group(2)))

    # Strip old header through first story (or first --- before story)
    intro = (
        "A curated list of **non-trivial technical war stories**, capturing real lessons "
        "suitable for **senior-level interviews**."
    )
    title = file_name.replace(".md", "")
    start_idx = 0
    for i, ln in enumerate(lines):
        if STORY_H2_RE.match(ln):
            start_idx = i
            break
    body_lines = lines[start_idx:]

    new_lines: list[str] = []
    for ln in body_lines:
        m_story = STORY_H2_RE.match(ln)
        if m_story:
            num = m_story.group(1)
            rest = m_story.group(2)
            new_lines.append(
                f'<h2 id="war-story-{num}" {H2_STORY_STYLE}>{num}. {rest}</h2>'
            )
            continue
        m_sub = SUBSECTION_H3_RE.match(ln)
        if m_sub:
            snum, ssub, rest = m_sub.group(1), m_sub.group(2), m_sub.group(3)
            new_lines.append(
                f'<h3 id="war-story-{snum}-sec-{ssub}" {H3_STYLE}>{snum}.{ssub} {rest}</h3>'
            )
            continue
        new_lines.append(ln)

    body = "\n".join(new_lines)
    if body and not body.endswith("\n"):
        body += "\n"
    body = _tag_untagged_fences(body)
    body = _convert_md_tables(body)

    return _build_front_matter(file_name, title, intro, stories) + body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[
            Path("docs/war_stories/WAR_STORIES_AWS.md"),
            Path("docs/war_stories/WAR_STORIES_CLOUD_SHARED.md"),
            Path("docs/war_stories/WAR_STORIES_GCP.md"),
            Path("docs/war_stories/WAR_STORIES_OTHER.md"),
        ],
    )
    parser.add_argument("--check", action="store_true", help="Exit 1 if file would change")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    changed_any = False
    for rel in args.paths:
        path = rel if rel.is_absolute() else repo / rel
        original = path.read_text(encoding="utf-8")
        updated = beautify(original, path.name)
        if updated != original:
            changed_any = True
            if args.check:
                print(f"would change: {path}", file=sys.stderr)
            else:
                path.write_text(updated, encoding="utf-8")
                print(f"updated: {path}")
        else:
            print(f"unchanged: {path}")
    return 1 if args.check and changed_any else 0


if __name__ == "__main__":
    raise SystemExit(main())

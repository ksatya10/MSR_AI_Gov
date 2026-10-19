# Shared regex patterns and git helpers used by the other scripts.

from __future__ import annotations

import re
import subprocess
from pathlib import Path


AI_TOOL_PKG = (
    r"(?:ai|chatgpt|gpt[- ]?(?:3(?:\.5)?|4(?:\.1)?|5)?|openai|claude(?:\s+code)?|"
    r"anthropic|copilot|codex|cursor|llm|large language model|gemini|bard|aider|"
    r"windsurf|devin)"
)

AI_TOOL_EXT = AI_TOOL_PKG[:-1] + r"|jules|goose|antigravity|grok|kiro|wchat)"

AI_DISCOVERY_TERMS = re.compile(
    r"(?i)(\bAI\b|\bA\.I\.\b|\bLLM\b|artificial intelligence|"
    r"large language model|generative ai|genai|machine[- ]generated|"
    r"chatgpt|openai|claude|anthropic|copilot|codex|cursor|gemini|bard|"
    r"aider|windsurf|devin|coding agent|ai[- ]agent|ai[- ]generated|"
    r"ai[- ]assisted|assisted-by|generated-by|vibe[- ]cod)"
)

NORMATIVE_TERMS = re.compile(
    r"(?i)\b(must|shall|should|required?|require[sd]?|expected to|may not|"
    r"do not|don't|prohibit\w*|not accept\w*|disclos\w+|discourag\w+|"
    r"responsib\w+|accountab\w+|polic(?:y|ies)|guidelines?|permitted|"
    r"allowed|banned|forbidden)\b"
)


TRAILER_ASSISTED_BY = re.compile(r"(?im)^[ \t]*Assisted-by[ \t]*:[ \t]*(.*)$")
TRAILER_GENERATED_BY = re.compile(r"(?im)^[ \t]*Generated-by[ \t]*:[ \t]*(.*)$")

TRAILER_COAUTHORED_AI = re.compile(
    rf"(?im)^[ \t]*Co-authored-by[ \t]*:.*\b{AI_TOOL_EXT}\b.*$"
)

TRAILER_SIGNED_OFF = re.compile(r"(?im)^[ \t]*Signed-off-by[ \t]*:[ \t]*(.*)$")

DET_ASSISTED_BY = r"(?im)^[ \t]*Assisted-by[ \t]*:"
DET_GENERATED_BY = r"(?im)^[ \t]*Generated-by[ \t]*:"
DET_SIGNED_OFF = r"(?im)^[ \t]*Signed-off-by[ \t]*:"
TRAILER_SIGNED_OFF_AI = re.compile(
    rf"(?im)^[ \t]*Signed-off-by[ \t]*:.*\b{AI_TOOL_EXT}\b.*$"
)

FMT_STRICT = re.compile(r"^[^\s:]+:[^\s]+")
FMT_LENIENT = re.compile(r"^[^:]+:\S")

TRAILER_KEY_ANY = re.compile(r"(?im)^[ \t]*([A-Za-z][A-Za-z0-9 _-]{2,40})[ \t]*:[ \t]*(.+)$")
TRAILER_KEYS_STANDARD = {
    "signed-off-by", "co-authored-by", "fixes", "closes", "close", "link",
    "reviewed-by", "tested-by", "acked-by", "suggested-by", "reported-by",
    "cc", "upstream", "change-id", "origin", "backport", "ref", "see-also",
    "depends-on", "bug", "issue",
}

HUMAN_AI_DOMAIN = re.compile(
    r"(?i)@(?:[a-z0-9-]+\.)*(?:openai\.com|anthropic\.com|sanctuary\.ai|"
    r"deepgate\.ai|[a-z0-9-]+\.ai|[a-z0-9-]+\.aero)\b"
)


RST_UNDERLINE = re.compile(r"^([=\-`:'\"~^_*+#<>])\1{2,}\s*$")
MD_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


def split_sections(text: str, path: str) -> list[tuple[str, int, str]]:
    lines = text.split("\n")
    marks: list[tuple[int, str, int]] = []

    if path.lower().endswith((".rst", ".txt")):
        order: list[str] = []
        for i in range(1, len(lines)):
            prev, cur = lines[i - 1], lines[i]
            if (RST_UNDERLINE.match(cur) and prev.strip()
                    and not RST_UNDERLINE.match(prev)
                    and len(cur.strip()) >= len(prev.strip()) - 2):
                ch = cur.strip()[0]
                if ch not in order:
                    order.append(ch)
                marks.append((i - 1, prev.strip(), order.index(ch) + 1))
    else:
        for i, ln in enumerate(lines):
            m = MD_HEADING.match(ln)
            if m:
                marks.append((i, m.group(2), len(m.group(1))))

    if not marks:
        return [("(whole file)", 0, text)]

    out = []
    for n, (idx, title, lvl) in enumerate(marks):
        end = len(lines)
        for idx2, _t, lvl2 in marks[n + 1:]:
            if lvl2 <= lvl:
                end = idx2
                break
        out.append((title, lvl, "\n".join(lines[idx:end]).strip()))
    return out


UNIT_SEP, REC_SEP = "\x1f", "\x1e"


def git(repo: Path, *args: str, timeout: int = 600) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, capture_output=True, text=True, errors="replace",
        timeout=timeout,
    )
    return proc.stdout


def git_log_records(repo: Path, since: str, path: str | None = None,
                    until: str | None = None) -> list[dict]:
    fmt = (f"%x1f%H%x1f%cI%x1f%aI%x1f%an%x1f%ae%x1f%cn%x1f%ce%x1f%s%x1f%B%x1e")
    args = ["log", f"--since={since}", f"--format={fmt}", "--no-merges"]
    if until:
        args.append(f"--until={until}")
    if path:
        args += ["--", path]
    raw = git(repo, *args)
    cols = ["sha", "commit_date", "author_date", "author_name", "author_email",
            "committer_name", "committer_email", "subject", "message"]
    out = []
    for rec in raw.split(REC_SEP):
        rec = rec.strip("\n")
        if not rec.strip():
            continue
        parts = rec.split(UNIT_SEP)
        parts = parts[1:] if parts and parts[0] == "" else parts
        if len(parts) < len(cols):
            continue
        row = dict(zip(cols, parts[:len(cols) - 1]))
        row["message"] = UNIT_SEP.join(parts[len(cols) - 1:])
        out.append(row)
    return out


def iso_week_monday(ts) -> str:
    import pandas as pd
    return (pd.to_datetime(ts, utc=True, format="mixed")
            .tz_localize(None).to_period("W-SUN").start_time.strftime("%Y-%m-%d"))

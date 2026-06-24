from __future__ import annotations

import re


DEFAULT_IM_SEGMENT_LIMIT = 3500
DEFAULT_DIGEST_BUDGET = 1200

_FENCE_START_RE = re.compile(r"^(?P<indent> {0,3})(?P<fence>`{3,}|~{3,})")


def sanitize_for_im(text: object) -> str:
    """Remove control characters that commonly break IM payloads."""
    value = "" if text is None else str(text)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = []
    for ch in value:
        code = ord(ch)
        if ch in ("\n", "\t"):
            cleaned.append(ch)
        elif code < 32 or code == 127 or 0x80 <= code <= 0x9F:
            continue
        else:
            cleaned.append(ch)
    result = "".join(cleaned)
    return result if result.strip() else "..."


def build_digest(text: object, budget: int = DEFAULT_DIGEST_BUDGET) -> str:
    """Build a deterministic short preview that never exceeds budget chars."""
    if budget <= 0:
        raise ValueError("budget must be positive")
    value = sanitize_for_im(text)
    if len(value) <= budget:
        return value
    if budget == 1:
        return "…"
    omitted = len(value) - budget
    marker = f"\n\n… [omitted {omitted} chars]"
    if len(marker) >= budget:
        return value[: budget - 1] + "…"
    head_budget = budget - len(marker)
    return value[:head_budget].rstrip() + marker


def segment_markdown(text: object, limit: int = DEFAULT_IM_SEGMENT_LIMIT) -> list[str]:
    """Split markdown into ordered chunks, preserving exact text content.

    Fenced code blocks are kept whole when a block fits inside the limit. Blocks
    larger than the limit are split at line boundaries where possible.
    """
    if limit <= 0:
        raise ValueError("limit must be positive")
    value = "" if text is None else str(text)
    if len(value) <= limit:
        return [value]

    chunks: list[str] = []
    current = ""
    for block, is_fence in _markdown_blocks(value):
        if len(block) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_exact(block, limit))
            continue
        if current and len(current) + len(block) > limit:
            chunks.append(current)
            current = ""
        current += block
    if current or not chunks:
        chunks.append(current)
    return chunks


def _markdown_blocks(text: str) -> list[tuple[str, bool]]:
    lines = text.splitlines(keepends=True)
    blocks: list[tuple[str, bool]] = []
    normal: list[str] = []
    i = 0
    while i < len(lines):
        marker = _fence_marker(lines[i])
        if marker is None:
            normal.append(lines[i])
            i += 1
            continue

        if normal:
            blocks.append(("".join(normal), False))
            normal = []

        char, size = marker
        fence_lines = [lines[i]]
        i += 1
        while i < len(lines):
            fence_lines.append(lines[i])
            if _is_fence_close(lines[i], char, size):
                i += 1
                break
            i += 1
        blocks.append(("".join(fence_lines), True))

    if normal:
        blocks.append(("".join(normal), False))
    return blocks


def _fence_marker(line: str) -> tuple[str, int] | None:
    match = _FENCE_START_RE.match(line)
    if not match:
        return None
    fence = match.group("fence")
    return fence[0], len(fence)


def _is_fence_close(line: str, char: str, size: int) -> bool:
    stripped = line.strip()
    return len(stripped) >= size and set(stripped) == {char}


def _split_exact(text: str, limit: int) -> list[str]:
    parts: list[str] = []
    rest = text
    threshold = max(1, int(limit * 0.5))
    while len(rest) > limit:
        cut = rest.rfind("\n\n", 0, limit)
        if cut >= threshold:
            cut += 2
        else:
            cut = rest.rfind("\n", 0, limit)
            if cut >= threshold:
                cut += 1
            else:
                cut = limit
        parts.append(rest[:cut])
        rest = rest[cut:]
    if rest:
        parts.append(rest)
    return parts

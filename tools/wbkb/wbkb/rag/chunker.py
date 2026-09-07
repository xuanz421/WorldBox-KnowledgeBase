"""Structure-aware markdown chunker (v1).

Splitting strategy, in order:
  1. ATX headings (# ... ######), fence-aware so ``` code blocks containing
     "#" lines are never mistaken for headings, build heading paths.
  2. Each section (heading -> next heading) becomes one chunk when small.
  3. Oversized sections are re-split by greedy paragraph packing (blank-line
     boundaries, fences kept intact); oversized paragraphs fall back to
     sentence boundaries.

chunk_id is position-derived (chunker version + path + section + sequence),
so editing one section never renumbers other sections; content changes are
detected via content_hash.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .schema import CHUNKER_VERSION, Chunk

MAX_SECTION_CHARS = 2000   # sections larger than this get secondary splitting
TARGET_CHUNK_CHARS = 1600  # packing target for secondary chunks
MIN_CHUNK_CHARS = 20       # drop near-empty chunks

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_FENCE_CLOSE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})\s*$")
_BLANK_RE = re.compile(r"^\s*$")
_SENTENCE_END_RE = re.compile(r"(?<=[.!?。！？；;])\s+")

SECTION_SEP = " > "


def _sha16(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _detect_heading_lines(lines: list[str]) -> list[tuple[int, int, str]]:
    """(line_index, level, title) for real ATX headings, skipping code fences."""
    headings: list[tuple[int, int, str]] = []
    fence_marker = ""
    for index, line in enumerate(lines):
        if fence_marker:
            close = _FENCE_CLOSE_RE.match(line)
            if close and close.group(1)[0] == fence_marker[0] and len(close.group(1)) >= len(fence_marker):
                fence_marker = ""
            continue
        open_match = _FENCE_OPEN_RE.match(line)
        if open_match and line.strip():
            fence_marker = open_match.group(1)
            continue
        match = _HEADING_RE.match(line)
        if match:
            headings.append((index, len(match.group(1)), match.group(2).strip()))
    return headings


def _sections(lines: list[str], headings: list[tuple[int, int, str]]) -> list[tuple[list[str], list[str]]]:
    """(heading_path, body_lines) for every section, preamble included."""
    sections: list[tuple[list[str], list[str]]] = []
    stack: list[tuple[int, str]] = []
    bounds: list[tuple[int, int]] = []
    if headings:
        first = headings[0][0]
        if first > 0:
            sections.append(([], lines[:first]))
        for position, (line_index, level, _title) in enumerate(headings):
            end = headings[position + 1][0] if position + 1 < len(headings) else len(lines)
            bounds.append((line_index + 1, end))
    else:
        sections.append(([], lines[:]))
        return sections

    for (line_index, level, title), (start, end) in zip(headings, bounds):
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        sections.append(([t for _lvl, t in stack], lines[start:end]))
    return sections


def _split_paragraphs(lines: list[str]) -> list[str]:
    """Blank-line separated paragraphs; fence lines stay glued to their block."""
    paragraphs: list[str] = []
    current: list[str] = []
    fence_marker = ""
    for line in lines:
        if fence_marker:
            current.append(line)
            close = _FENCE_CLOSE_RE.match(line)
            if close and close.group(1)[0] == fence_marker[0] and len(close.group(1)) >= len(fence_marker):
                fence_marker = ""
            continue
        open_match = _FENCE_OPEN_RE.match(line)
        if open_match and line.strip():
            fence_marker = open_match.group(1)
            current.append(line)
            continue
        if _BLANK_RE.match(line):
            if current:
                paragraphs.append("\n".join(current).rstrip())
                current = []
            continue
        current.append(line)
    if current:
        paragraphs.append("\n".join(current).rstrip())
    return [p for p in paragraphs if p.strip()]


def _split_sentences(paragraph: str) -> list[str]:
    parts = [p.strip() for p in _SENTENCE_END_RE.split(paragraph) if p.strip()]
    return parts if parts else [paragraph]


def _pack_greedy(units: list[str], joiner: str) -> list[str]:
    """Greedily pack units into chunks of at most MAX_SECTION_CHARS."""
    packed: list[str] = []
    current: list[str] = []
    current_len = 0
    for unit in units:
        extra = len(unit) + (len(joiner) if current else 0)
        if current and current_len + extra > TARGET_CHUNK_CHARS:
            packed.append(joiner.join(current))
            current, current_len = [], 0
            extra = len(unit)
        current.append(unit)
        current_len += extra
    if current:
        packed.append(joiner.join(current))
    return packed


def _split_oversized(paragraph: str) -> list[str]:
    """A single paragraph above the limit: sentence-boundary packing."""
    sentences = _split_sentences(paragraph)
    packed = _pack_greedy(sentences, " ")
    # last-resort hard cuts for pathological single sentences
    out: list[str] = []
    for piece in packed:
        while len(piece) > MAX_SECTION_CHARS:
            out.append(piece[:MAX_SECTION_CHARS])
            piece = piece[MAX_SECTION_CHARS:]
        if piece.strip():
            out.append(piece)
    return out


def _chunk_section_text(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    if len(stripped) <= MAX_SECTION_CHARS:
        return [stripped]
    paragraphs = _split_paragraphs(stripped.splitlines())
    units: list[str] = []
    for paragraph in paragraphs:
        if len(paragraph) <= MAX_SECTION_CHARS:
            units.append(paragraph)
        else:
            units.extend(_split_oversized(paragraph))
    # paragraphs themselves become the packing units for oversized sections
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for unit in units:
        if len(unit) >= TARGET_CHUNK_CHARS:
            if current:
                chunks.append("\n\n".join(current))
                current, current_len = [], 0
            chunks.append(unit)
            continue
        extra = len(unit) + (2 if current else 0)
        if current and current_len + extra > MAX_SECTION_CHARS:
            chunks.append("\n\n".join(current))
            current, current_len = [], 0
            extra = len(unit)
        current.append(unit)
        current_len += extra
    if current:
        chunks.append("\n\n".join(current))
    return [c for c in chunks if len(c.strip()) >= MIN_CHUNK_CHARS]


def chunk_markdown(text: str, source_path: str, document_type: str) -> list:
    """Chunk one markdown document. Deterministic: same input, same output."""
    lines = text.splitlines()
    headings = _detect_heading_lines(lines)
    title = ""
    for _idx, level, head_title in headings:
        if level == 1:
            title = head_title
            break
    if not title and headings:
        title = headings[0][2]
    if not title:
        title = Path(source_path).stem

    chunks = []
    per_section_seq: dict[str, int] = {}
    for heading_path, body_lines in _sections(lines, headings):
        section_text = "\n".join(body_lines).strip()
        if not section_text:
            continue
        section_str = SECTION_SEP.join(heading_path)
        for piece in _chunk_section_text(section_text):
            if len(piece.strip()) < MIN_CHUNK_CHARS:
                continue
            seq = per_section_seq.get(section_str, 0)
            per_section_seq[section_str] = seq + 1
            chunk_id = _sha16(f"{CHUNKER_VERSION}\x1f{source_path}\x1f{section_str}\x1f{seq}")
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    document_type=document_type,
                    source_path=source_path,
                    title=title,
                    section=section_str,
                    text=piece,
                    content_hash=_sha16(piece),
                )
            )
    return chunks

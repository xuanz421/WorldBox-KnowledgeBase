#!/usr/bin/env python3
"""Structural validation for the pattern library (Z6 §34)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = ROOT / "knowledge" / "patterns"

problems: list[str] = []

catalog = json.loads((PATTERNS / "catalog.json").read_text(encoding="utf-8"))
entries = catalog["patterns"]
if len(entries) != 16:
    problems.append(f"catalog has {len(entries)} patterns, expected 16")

ids = [entry["id"] for entry in entries]
if len(set(ids)) != len(ids):
    problems.append("duplicate pattern ids")

ALLOWED_STATUS = {"Strong Verified", "Verified", "Mostly Verified", "Inferred"}
ALLOWED_CATEGORY = {"Assets", "Actor", "Kingdom", "Buildings", "Jobs", "Resources",
                    "Items", "UI", "Persistence", "Lifecycle", "Patching", "Utility"}

# reference mod ids known from the Z5 catalogue
ref_catalog = json.loads((ROOT / "knowledge" / "reference-mods" / "catalog.json").read_text(encoding="utf-8"))
known_refs = {entry["source_id"] for entry in ref_catalog}

for entry in entries:
    path = PATTERNS / entry["file"]
    if not path.is_file():
        problems.append(f"{entry['id']}: missing file {entry['file']}")
        continue
    text = path.read_text(encoding="utf-8")
    for section in ("# Pattern:", "## Status", "## Goal", "## When to Use", "## Relevant Systems",
                    "## Implementation Flow", "## Reference Implementations", "## Caveats",
                    "## Evidence", "## Provenance"):
        if section not in text:
            problems.append(f"{entry['id']}: missing section {section}")
    if entry["status"] not in ALLOWED_STATUS:
        problems.append(f"{entry['id']}: bad status {entry['status']}")
    if entry["category"] not in ALLOWED_CATEGORY:
        problems.append(f"{entry['id']}: bad category {entry['category']}")
    if entry["tier"] not in {"S", "A"}:
        problems.append(f"{entry['id']}: bad tier {entry['tier']}")
    for ref in entry["references"]:
        if ref not in known_refs:
            problems.append(f"{entry['id']}: unknown reference mod {ref}")
    # every pattern must cite at least one file:line style evidence
    if not re.search(r"\.cs:\d+", text):
        problems.append(f"{entry['id']}: no file:line evidence found")
    if "Unverified" not in text and "NML evidence" in text and "None" not in text:
        pass  # informational only

# Inferred patterns must not be in the default index
inferred = [e["id"] for e in entries if e["status"] == "Inferred"]
if inferred:
    problems.append(f"Inferred patterns must stay out of the library: {inferred}")

# stray pattern files not in catalog
catalog_files = {e["file"] for e in entries}
actual_files = {str(p.relative_to(PATTERNS)).replace("\\", "/")
                for p in PATTERNS.glob("*/*.md")}
if actual_files != catalog_files:
    problems.append(f"file set mismatch: {actual_files ^ catalog_files}")

if problems:
    print("FAILED:")
    for problem in problems:
        print(f"  - {problem}")
    sys.exit(1)
print(f"OK: {len(entries)} patterns structurally valid "
      f"({sum(1 for e in entries if e['status']=='Strong Verified')} Strong Verified / "
      f"{sum(1 for e in entries if e['status']=='Verified')} Verified)")

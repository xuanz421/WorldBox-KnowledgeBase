#!/usr/bin/env python3
"""Consistency validation for the reference-mod knowledge catalogue (Z5 §33)."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "knowledge" / "reference-mods"

problems: list[str] = []

catalog = json.loads((OUT / "catalog.json").read_text(encoding="utf-8"))
profiles = sorted(p.name for p in (OUT / "mods").glob("*.md"))
csv_rows = list(csv.DictReader(open(OUT / "catalog.csv", encoding="utf-8")))
matrix = list(csv.DictReader(open(OUT / "system-matrix.csv", encoding="utf-8")))
patterns = [json.loads(line) for line in (OUT / "pattern-candidates.jsonl").read_text(encoding="utf-8").splitlines() if line]

if len(catalog) != 21:
    problems.append(f"catalog has {len(catalog)} entries, expected 21")
if len(profiles) != len(catalog):
    problems.append(f"{len(profiles)} profiles vs {len(catalog)} catalog entries")

catalog_ids = {entry["source_id"] for entry in catalog}
profile_ids = {f"ref:{p[:-3]}" for p in profiles}
if catalog_ids != profile_ids:
    problems.append(f"id mismatch: {catalog_ids ^ profile_ids}")

for entry in catalog:
    link = OUT / entry["profile"]
    if not link.is_file():
        problems.append(f"broken profile link: {entry['profile']}")
    if not entry["primary_systems"]:
        problems.append(f"{entry['source_id']}: no primary system")

if len(csv_rows) != len(catalog):
    problems.append(f"catalog.csv rows {len(csv_rows)} != {len(catalog)}")
csv_ids = {row["mod_id"] for row in csv_rows}
if csv_ids != catalog_ids:
    problems.append("catalog.csv ids differ from catalog.json")

matrix_ids = {row["mod_id"] for row in matrix}
if not matrix_ids <= catalog_ids:
    problems.append(f"matrix has unknown ids: {matrix_ids - catalog_ids}")
for entry in catalog:
    matrix_primary = {row["system"] for row in matrix if row["mod_id"] == entry["source_id"] and row["role"] == "primary"}
    if matrix_primary != set(entry["primary_systems"]):
        problems.append(f"{entry['source_id']}: matrix primary {matrix_primary} != catalog {set(entry['primary_systems'])}")

known_systems = {"Actor", "Traits", "Jobs", "City", "Kingdom", "Diplomacy", "Culture", "Religion",
                 "Buildings", "Resources", "Items", "Combat", "World", "Map", "Events", "Assets",
                 "UI", "Save/Persistence", "Mod Lifecycle", "Utility", "Localization", "Events",
                 "Alliance", "Clan", "War", "AI", "Items"}
for row in matrix:
    if row["system"] not in known_systems:
        problems.append(f"unknown system name in matrix: {row['system']}")

for pattern in patterns:
    if pattern["mod_id"] not in catalog_ids:
        problems.append(f"pattern references unknown mod: {pattern['mod_id']}")

allowed_conf = {"Verified", "Mostly Verified", "Partial"}
for entry in catalog:
    if entry["confidence"] not in allowed_conf:
        problems.append(f"{entry['source_id']}: bad confidence {entry['confidence']}")

if problems:
    print("FAILED:")
    for problem in problems:
        print(f"  - {problem}")
    sys.exit(1)
print(f"OK: {len(catalog)} mods / {len(profiles)} profiles / {len(matrix)} matrix rows / "
      f"{len(patterns)} patterns consistent")

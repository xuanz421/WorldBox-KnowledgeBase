"""Shared helpers: hashing, path records, reference-mod ID normalization."""

from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path

# Trailing version-like suffix stripped from reference-mod directory names,
# applied repeatedly: "_1.8.0", "0.51.0+", "_1.5.0new", "_beta1.1.3", "-pre"...
_VERSION_TAIL = re.compile(
    r"[_\-\s]?(?:v|beta|alpha|pre|rc)?\d+(?:[._\-\s]\d+)*\+?"
    r"(?:[_\-\s]?(?:new|final|stable|pre|beta|alpha|rc))?$",
    re.IGNORECASE,
)


def normalize_ref_name(name: str) -> str:
    """Normalize a reference-mod directory name into a stable ID part.

    Lowercases, strips trailing version-like suffixes, maps spaces and
    underscores to "-". Deterministic; never empty.
    """
    fallback = name.strip().lower().replace(" ", "-")
    s = fallback
    prev = None
    while prev != s:
        prev = s
        s = _VERSION_TAIL.sub("", s).rstrip("_- ")
    s = s.replace("_", "-")
    return s or fallback


def ref_source_id(dir_name: str) -> str:
    return f"ref:{normalize_ref_name(dir_name)}"


def sha256_file(path: str | os.PathLike, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def file_record(path: str | os.PathLike) -> dict:
    p = Path(path)
    st = p.stat()
    return {
        "path": str(p.resolve()),
        "filename": p.name,
        "size": st.st_size,
        "mtime": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(timespec="seconds"),
        "sha256": sha256_file(p),
    }


def now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def dir_stats(root: str | os.PathLike, exclude_dirs: tuple[str, ...] = (".git",)) -> dict:
    """Cheap single-walk directory fingerprint (no per-file hashing)."""
    file_count = 0
    total_size = 0
    latest_mtime = 0.0
    csharp = 0
    projects = 0
    assemblies = 0
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for fn in files:
            fp = os.path.join(base, fn)
            try:
                st = os.stat(fp)
            except OSError:
                continue
            file_count += 1
            total_size += st.st_size
            latest_mtime = max(latest_mtime, st.st_mtime)
            ext = os.path.splitext(fn)[1].lower()
            if ext == ".cs":
                csharp += 1
            elif ext in (".csproj", ".sln"):
                projects += 1
            elif ext == ".dll":
                assemblies += 1
    return {
        "file_count": file_count,
        "total_size": total_size,
        "latest_mtime": datetime.fromtimestamp(latest_mtime, tz=timezone.utc).isoformat(timespec="seconds")
        if latest_mtime
        else None,
        "csharp_file_count": csharp,
        "project_files": projects,
        "assembly_files": assemblies,
    }

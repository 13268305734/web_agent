from __future__ import annotations

from datetime import datetime
from pathlib import Path


def ensure_dir(path: str | Path) -> Path:
    """Create a directory if it does not exist and return it as Path."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def utc_timestamp_for_filename() -> str:
    """Return a compact UTC timestamp safe for filenames."""
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def safe_filename(value: str, max_len: int = 80) -> str:
    """Convert arbitrary text into a simple filename-safe string."""
    allowed = []
    for ch in value:
        if ch.isalnum() or ch in ("-", "_", "."):
            allowed.append(ch)
        elif ch.isspace():
            allowed.append("_")
    name = "".join(allowed).strip("._")
    return (name or "file")[:max_len]

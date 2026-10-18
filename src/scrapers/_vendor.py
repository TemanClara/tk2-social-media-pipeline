"""Memuat library omkarcloud dari folder third_party/.

Kedua library memakai nama modul tingkat atas yang sama (`config`,
`scraper_errors`, `schema_fields`). Karena itu hanya satu library yang boleh
dimuat dalam satu proses. Satu run memang hanya untuk satu platform.
"""

from __future__ import annotations

import sys
from pathlib import Path

THIRD_PARTY = Path(__file__).resolve().parents[2] / "third_party"

_LOADED: str | None = None


def load(name: str) -> None:
    """Tambahkan third_party/omkarcloud-<name>-scraper ke sys.path."""
    global _LOADED
    if _LOADED == name:
        return
    if _LOADED is not None:
        raise RuntimeError(
            f"Library {_LOADED} sudah dimuat; {name} tidak bisa dimuat di proses yang sama."
        )
    path = THIRD_PARTY / f"omkarcloud-{name}-scraper"
    if not path.is_dir():
        raise RuntimeError(f"Folder {path} tidak ditemukan. Lihat third_party/README.md.")
    sys.path.insert(0, str(path))
    _LOADED = name

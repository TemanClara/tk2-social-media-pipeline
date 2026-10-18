"""Perlengkapan bersama untuk tes: pengaturan, logger, dan arsip tiruan."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from src.common.config import Settings
from src.scrapers._common import RunOptions

# Selalu pakai salt tes, apa pun isi .env, supaya hasil tes tidak bergantung
# pada .env masing-masing anggota tim.
os.environ["PSEUDONYM_SALT"] = "salt-khusus-tes"

KEYWORDS = {
    "periode": {"mulai": "2024-10-01", "selesai": "2026-09-30"},
    "peristiwa_pemicu": [{"nama": "a", "tanggal": "2024-10-20", "jendela_hari": 14}],
    "kata_kunci": ["Mayor Teddy"],
    "hashtag": ["mayorteddy"],
    "akun_target": {"tiktok": ["akunfan"], "instagram": ["akunberita"], "x": []},
    "bahasa": {"utama": "id", "sertakan_non_indonesia": False},
}

SETTINGS = Settings(request_delay_seconds=0.0, max_retries=1, data_dir=Path("/tmp/tk2-tes"))
LOGGER = logging.getLogger("tk2-tes")
LOGGER.addHandler(logging.NullHandler())
LOGGER.propagate = False


class FakeArchive:
    def __init__(self):
        self.saved = []

    def save(self, payload, *, label="page"):
        self.saved.append((label, payload))


def make(scraper_cls, options=None, **kwargs):
    archive = FakeArchive()
    scraper = scraper_cls(SETTINGS, KEYWORDS, LOGGER, archive=archive, **kwargs)
    scraper.options = options or RunOptions(max_pages=3, comment_pages=2)
    return scraper, archive


def pages(*page_list):
    """Fungsi tiruan berhalaman: cursor None -> halaman 1, "2" -> halaman 2, dst."""
    calls = []
    kwargs_seen = []

    def fetch(value, cursor, **kwargs):
        calls.append((value, cursor))
        kwargs_seen.append(kwargs)
        index = int(cursor) - 1 if cursor else 0
        items = page_list[index]
        has_more = index + 1 < len(page_list)
        return {**items, "next_cursor": str(index + 2) if has_more else None, "has_more": has_more}

    fetch.calls = calls
    fetch.kwargs = kwargs_seen
    return fetch

"""Kontrak yang dipakai bersama oleh scraper ketiga platform.

Setiap scraper mengembalikan dict dengan kunci yang sama supaya modul
deduplikasi dan pemetaan skema (bagian C4) tidak perlu menangani tiga
bentuk data yang berbeda.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator

# Skema terpadu lintas platform.
# SUMBER: skema dataset (Nafia, C4) dan daftar atribut (Azzahra, C1).
# Samakan isinya setelah CP1; ubah di sini saja, jangan di tiap scraper.
UNIFIED_FIELDS = [
    "platform",        # "tiktok" | "instagram" | "x"
    "item_type",       # "post" | "comment" | "reply" | "quote"
    "item_id",         # ID unik di platform asal
    "parent_id",       # ID unggahan/komentar induk; None bila post utama
    "conversation_id", # ID percakapan; dipakai untuk RQ3 di X
    "author_hash",     # username yang sudah dipseudonimkan (lihat C6)
    "text",
    "created_at",      # ISO 8601
    "like_count",
    "reply_count",
    "share_count",
    "view_count",      # jumlah tayang/putar; kosong untuk komentar dan bila tidak tersedia
    "hashtags",        # daftar hashtag di teks, huruf kecil tanpa '#'
    "language",        # kode bahasa dari platform (X, TikTok); kosong untuk Instagram
    "url",
    "query",           # kata kunci/hashtag/akun yang memunculkan record ini
]


class BaseScraper(ABC):
    """Turunkan kelas ini untuk tiap platform."""

    platform: str = "base"

    def __init__(self, settings, keywords: dict, logger, archive=None):
        self.settings = settings
        self.keywords = keywords
        self.logger = logger
        # Simpan respons asli lewat self.archive.save(payload) SEBELUM diparsing,
        # supaya kesalahan parsing bisa diperbaiki tanpa scraping ulang.
        self.archive = archive

    @abstractmethod
    def collect(self, limit: int | None = None) -> Iterator[dict]:
        """Hasilkan record satu per satu sesuai UNIFIED_FIELDS.

        Pakai `yield`, bukan mengumpulkan semuanya ke dalam list, supaya
        data tetap tertulis ke disk meski run berhenti di tengah jalan.
        """
        raise NotImplementedError

    def to_unified(self, **kwargs) -> dict:
        """Bentuk satu record lengkap; kolom yang tidak diisi bernilai None."""
        record = {field: None for field in UNIFIED_FIELDS}
        record["platform"] = self.platform
        record.update({k: v for k, v in kwargs.items() if k in record})
        return record

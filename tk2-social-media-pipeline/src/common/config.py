"""Memuat pengaturan dari .env dan config/keywords.yaml.

Semua parameter pengumpulan (kata kunci, periode, akun) dibaca dari
config/keywords.yaml supaya tidak ada nilai yang tertanam di dalam kode dan
isinya bisa ikut disalin ke manifest tiap run.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]

load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    request_delay_seconds: float
    max_retries: int
    data_dir: Path

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def interim_dir(self) -> Path:
        return self.data_dir / "interim"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            request_delay_seconds=float(os.getenv("REQUEST_DELAY_SECONDS", "2.0")),
            max_retries=int(os.getenv("MAX_RETRIES", "4")),
            data_dir=ROOT / os.getenv("DATA_DIR", "data"),
        )


def keywords_path() -> Path:
    return ROOT / "config" / "keywords.yaml"


def load_keywords(path: Path | None = None) -> dict:
    """Baca config/keywords.yaml."""
    with open(path or keywords_path(), "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_secret(name: str) -> str:
    """Ambil kredensial dari .env; berhenti dengan pesan jelas bila kosong."""
    value = os.getenv(name, "")
    if not value:
        raise RuntimeError(
            f"{name} belum diisi. Salin .env.example menjadi .env lalu isi nilainya."
        )
    return value

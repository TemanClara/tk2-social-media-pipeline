"""Penyimpanan hasil scraping dalam tiga lapis.

    data/raw/        respons apa adanya dari platform, belum diubah
    data/interim/    record yang sudah dipetakan ke skema terpadu (JSONL)
    data/processed/  dataset siap analisis (dihasilkan bagian C4)

Pemisahan raw dan interim dilakukan karena pengambilan ulang data media
sosial mahal dan belum tentu berhasil: unggahan bisa dihapus dan akses bisa
diblokir. Dengan menyimpan respons aslinya, kesalahan parsing yang baru
ketahuan belakangan dapat diperbaiki tanpa perlu scraping ulang.

Format interim: JSONL, satu objek JSON per baris, ditulis sambil jalan
sehingga data yang sudah terkumpul tetap aman bila run berhenti di tengah.
"""

from __future__ import annotations

import gzip
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("tk2")


class RawArchive:
    """Simpan respons mentah per halaman, dikompresi, untuk parsing ulang."""

    def __init__(self, raw_dir: Path, run_id: str):
        self.dir = Path(raw_dir) / run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self._page = 0

    def save(self, payload: str | bytes | dict, *, label: str = "page") -> Path:
        self._page += 1
        path = self.dir / f"{label}_{self._page:05d}.json.gz"
        if isinstance(payload, dict):
            payload = json.dumps(payload, ensure_ascii=False)
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        with gzip.open(path, "wb") as f:
            f.write(payload)
        return path

    @property
    def total(self) -> int:
        return self._page


class BatchWriter:
    """Tulis record ternormalisasi ke JSONL, dipecah tiap `batch_size` record."""

    def __init__(self, interim_dir: Path, run_id: str, batch_size: int = 500):
        self.out_dir = Path(interim_dir) / run_id
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id
        self.batch_size = batch_size
        self._count = 0
        self._batch_index = 0
        self._handle = None
        self._open_new_batch()

    def _open_new_batch(self) -> None:
        if self._handle:
            self._handle.close()
        self._batch_index += 1
        path = self.out_dir / f"batch_{self._batch_index:04d}.jsonl"
        self._handle = open(path, "a", encoding="utf-8")
        logger.info("Menulis ke %s", path)

    def write(self, record: dict) -> None:
        record.setdefault("_scraped_at", datetime.now(timezone.utc).isoformat())
        record.setdefault("_run_id", self.run_id)
        self._handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._handle.flush()
        self._count += 1
        if self._count % self.batch_size == 0:
            self._open_new_batch()

    @property
    def total(self) -> int:
        return self._count

    def close(self) -> None:
        if self._handle:
            self._handle.close()
            self._handle = None

    def __enter__(self) -> "BatchWriter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


class SeenStore:
    """Catatan ID yang sudah diambil, agar run yang terputus bisa dilanjutkan.

    Berkas ini hidup lintas run (tidak di dalam folder run), sehingga
    pengumpulan bertahap pada platform yang sama tidak mengambil ulang
    unggahan yang sudah masuk.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seen: set[str] = set()
        if self.path.exists():
            self._seen = {
                line.strip()
                for line in self.path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            }
            logger.info("%d ID sudah pernah diambil sebelumnya.", len(self._seen))
        self._handle = open(self.path, "a", encoding="utf-8")

    def __contains__(self, item_id: str) -> bool:
        return item_id in self._seen

    def __len__(self) -> int:
        return len(self._seen)

    def add(self, item_id: str) -> None:
        if item_id not in self._seen:
            self._seen.add(item_id)
            self._handle.write(item_id + "\n")
            self._handle.flush()

    def close(self) -> None:
        self._handle.close()

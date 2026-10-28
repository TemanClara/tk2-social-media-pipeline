"""Catatan asal-usul tiap run pengumpulan data.

Setiap run menghasilkan satu manifest.json berisi parameter yang dipakai,
jumlah data yang masuk, dan waktu pelaksanaan. Gunanya ada dua. Pertama,
setiap angka jumlah data bisa ditelusuri ke run tertentu. Kedua, salinan
isi config/keywords.yaml ikut disimpan, sehingga run lama tetap dapat
dijelaskan meski parameternya sudah berubah sejak itu.
"""

from __future__ import annotations

import json
import platform as platform_module
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


def _git_commit() -> str | None:
    """Commit yang sedang aktif, agar hasil run bisa dikaitkan ke versi kode."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() or None
    except Exception:
        return None


@dataclass
class RunManifest:
    run_id: str
    platform: str
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str | None = None
    status: str = "running"            # running | completed | interrupted | failed
    params: dict = field(default_factory=dict)
    keywords_snapshot: dict = field(default_factory=dict)
    counts: dict = field(default_factory=lambda: {
        "fetched": 0,       # diterima dari platform
        "written": 0,       # tersimpan sebagai record
        "duplicates": 0,    # dilewati karena sudah pernah diambil
        "errors": 0,
    })
    environment: dict = field(default_factory=lambda: {
        "python": platform_module.python_version(),
        "os": platform_module.platform(),
        "git_commit": _git_commit(),
    })

    def bump(self, key: str, n: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + n

    def finish(self, status: str) -> None:
        self.status = status
        self.finished_at = datetime.now(timezone.utc).isoformat()

    @property
    def duration_seconds(self) -> float | None:
        if not self.finished_at:
            return None
        start = datetime.fromisoformat(self.started_at)
        end = datetime.fromisoformat(self.finished_at)
        return round((end - start).total_seconds(), 1)

    def save(self, path: Path) -> None:
        data = asdict(self)
        data["duration_seconds"] = self.duration_seconds
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

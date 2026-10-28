"""Rekap seluruh run menjadi satu tabel.

Dipakai sebagai sumber tunggal angka jumlah data, supaya angka yang dilaporkan
selalu bisa ditelusuri ke manifest run.

    python -m src.summarize_runs
"""

from __future__ import annotations

import json

from src.common.config import Settings


def main() -> int:
    settings = Settings.from_env()
    rows = []
    for manifest_file in sorted(settings.interim_dir.glob("*/manifest.json")):
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
        counts = data.get("counts", {})
        rows.append({
            "run_id": data["run_id"],
            "platform": data["platform"],
            "status": data["status"],
            "mulai": data["started_at"][:19].replace("T", " "),
            "durasi_detik": data.get("duration_seconds"),
            "tersimpan": counts.get("written", 0),
            "duplikat": counts.get("duplicates", 0),
            "error": counts.get("errors", 0),
        })

    if not rows:
        print("Belum ada run yang tercatat di", settings.interim_dir)
        return 0

    headers = list(rows[0])
    widths = {h: max(len(h), *(len(str(r[h])) for r in rows)) for h in headers}
    line = " | ".join(h.ljust(widths[h]) for h in headers)
    print(line)
    print("-" * len(line))
    for r in rows:
        print(" | ".join(str(r[h]).ljust(widths[h]) for h in headers))

    total = sum(r["tersimpan"] for r in rows)
    print("-" * len(line))
    print(f"Total record tersimpan: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

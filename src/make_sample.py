"""Buat cuplikan teranonimisasi dari satu run, untuk data/sample/ dan docs/evidence/.

Contoh:
    python -m src.make_sample data/interim/tiktok_20261015_195636
    python -m src.make_sample data/interim/instagram_20261015_195605 --rows 30

Hasil:
    data/sample/<platform>_sample.json   cuplikan record (JSON)
    data/sample/<platform>_sample.csv    cuplikan yang sama (CSV, aman dibuka di Excel)
    docs/evidence/<platform>_<tanggal>_manifest.json   salinan manifest run

Username di record sudah berupa hash sejak scraping. Untuk repo publik,
cuplikan ini menyamarkan lebih jauh, karena teks dan tautan masih bisa
membawa ke identitas pengguna:
    - @mention di dalam teks diganti "@[pengguna]", juga bila run sudah memakai
      --mask-mentions (token @user_<hash> pun disamarkan untuk repo publik)
    - teks dipotong (bawaan 80 karakter), sesuai janji "kutipan pendek"
    - kolom url dikosongkan, karena tautan komentar membuka profil penulisnya
Aturan ini perlu dikonfirmasi bersama C6 (Clara).
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from src.common.anonymize import MENTION
from src.common.config import ROOT
from src.scrapers.base import UNIFIED_FIELDS

COLUMNS = UNIFIED_FIELDS + ["_scraped_at", "_run_id"]


def redact(text: str | None, max_chars: int) -> str | None:
    if text is None:
        return None
    text = MENTION.sub("@[pengguna]", text).replace("\n", " ").strip()
    return text if len(text) <= max_chars else text[:max_chars].rstrip() + "…"


def pick(records: list[dict], rows: int) -> list[dict]:
    """Semua post (maks. separuh jatah), lalu komentar/balasan dibagi rata per post."""
    posts = [r for r in records if r["item_type"] == "post"][: max(1, rows // 2)]
    others = [r for r in records if r["item_type"] != "post"]
    chosen = list(posts)
    by_parent: dict[str, list[dict]] = {}
    for r in others:
        by_parent.setdefault(r["conversation_id"] or "", []).append(r)
    queues = list(by_parent.values())
    while len(chosen) < rows and any(queues):
        for queue in queues:
            if queue and len(chosen) < rows:
                chosen.append(queue.pop(0))
    return chosen


def main() -> int:
    parser = argparse.ArgumentParser(description="Cuplikan teranonimisasi dari satu run")
    parser.add_argument("run_dir", type=Path, help="Folder data/interim/<run_id>")
    parser.add_argument("--rows", type=int, default=30, help="Jumlah baris cuplikan (bawaan 30)")
    parser.add_argument("--max-chars", type=int, default=80, help="Panjang maksimum teks (bawaan 80)")
    args = parser.parse_args()

    manifest = json.loads((args.run_dir / "manifest.json").read_text(encoding="utf-8"))
    platform = manifest["platform"]
    records = [json.loads(line)
               for path in sorted(args.run_dir.glob("batch_*.jsonl"))
               for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    sample = []
    for record in pick(records, args.rows):
        record = {key: record.get(key) for key in COLUMNS}
        record["text"] = redact(record["text"], args.max_chars)
        record["url"] = None
        sample.append(record)

    sample_dir = ROOT / "data" / "sample"
    sample_dir.mkdir(parents=True, exist_ok=True)
    json_path = sample_dir / f"{platform}_sample.json"
    json_path.write_text(json.dumps(sample, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    csv_path = sample_dir / f"{platform}_sample.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for row in sample:
            # daftar hashtag ditulis sebagai teks dipisah spasi agar rapi di Excel
            writer.writerow({**row, "hashtags": " ".join(row.get("hashtags") or [])})

    evidence_dir = ROOT / "docs" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    day = manifest["run_id"].split("_")[1]
    manifest_path = evidence_dir / f"{platform}_{day}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for path in (json_path, csv_path, manifest_path):
        print(f"Ditulis: {path.relative_to(ROOT)}")
    print(f"{len(sample)} baris dari {len(records)} record run {manifest['run_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

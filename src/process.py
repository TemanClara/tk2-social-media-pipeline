from __future__ import annotations

import argparse
import json
import platform as platform_module
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.common.anonymize import MENTION
from src.common.config import ROOT, Settings, load_keywords
from src.common.logging_setup import new_run_id, setup_logging
from src.common.manifest import _git_commit
from src.scrapers._common import date_ranges, extract_hashtags, in_ranges, parse_time
from src.scrapers.base import UNIFIED_FIELDS

VALID_PLATFORMS = ("x", "tiktok", "instagram")
VALID_ITEM_TYPES = ("post", "comment", "reply", "quote")
COUNT_FIELDS = ("like_count", "reply_count", "share_count", "view_count")
ID_FIELDS = ("item_id", "parent_id", "conversation_id")
NON_POST_TYPES = frozenset({"comment", "reply", "quote"})

# hash_username() menghasilkan 16 karakter hex huruf kecil.
HASH_PATTERN = re.compile(r"[0-9a-f]{16}")
URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
WORD_PATTERN = re.compile(r"[^\W\d_]{2,}")
MEDIA_PLACEHOLDER = re.compile(r"(?:\s*\[(?:foto|photo|gambar|image|stiker|sticker|gif|video)\]\s*)+",
                               re.IGNORECASE)

# --- Bahasa (kriteria inklusi: hanya berbahasa Indonesia) --------------------
#   - INDONESIAN       : dianggap bahasa Indonesia ("in" adalah kode lama X).
#   - AMBIGUOUS        : tidak ditandai. Melayu, Jawa, Sunda, dan Tagalog kerap
#                        tertukar dengan bahasa Indonesia informal; "und",
#                        "zxx", dan "q*" adalah kode X untuk teks tanpa bahasa
#                        yang jelas (emoji saja, tautan saja, mention saja).
#   - kode lain        : ditandai bukan Indonesia HANYA bila teksnya memuat
#                        paling sedikit MIN_WORDS_FOR_LANGUAGE kata. Teks lebih
#                        pendek terlalu sering salah deteksi.
# Distribusi kode lengkap tetap dilaporkan di report.md.
INDONESIAN_LANG = frozenset({"id", "in"})
# "un": TikTok memberi "un" bila bahasa tidak terdeteksi (6% komentar pada run
# 25 Okt 2026), jadi bukan bahasa asing.
AMBIGUOUS_LANG = frozenset({"ms", "jv", "su", "tl", "und", "un", "zxx",
                            "qam", "qct", "qht", "qme", "qst"})
MIN_WORDS_FOR_LANGUAGE = 3

# Kriteria eksklusi: record dengan salah satu flag ini tidak `eligible`.
EXCLUSION_FLAGS = {
    "flag_text_missing": "Teks kosong",
    "flag_non_indonesian": "Bukan bahasa Indonesia",
    "flag_mention_only": "Hanya menandai pengguna lain",
    "flag_repeated_by_author": "Komentar ganda dari akun yang sama",
    "flag_out_of_period": "Di luar periode",
    "flag_created_at_invalid": "Waktu tidak terbaca",
    "flag_author_not_hashed": "author_hash bukan hash (privasi)",
    "flag_item_type_invalid": "item_type tidak dikenal",
}
# Ditandai untuk informasi saja; record tetap eligible.
INFO_FLAGS = {
    "flag_parent_missing": "comment/reply/quote tanpa parent_id",
    "flag_conversation_missing": "Record X tanpa conversation_id (RQ3)",
    "flag_negative_count": "Angka engagement negatif (dikosongkan)",
}
ALL_FLAGS = list(EXCLUSION_FLAGS) + list(INFO_FLAGS)

OUTPUT_COLUMNS = (UNIFIED_FIELDS[:UNIFIED_FIELDS.index("text") + 1] + ["text_clean"]
                  + UNIFIED_FIELDS[UNIFIED_FIELDS.index("text") + 1:]
                  + ALL_FLAGS + ["eligible", "_scraped_at", "_run_id"])


# ------------------------------------------------------------- pilih run

@dataclass
class RunInfo:
    run_id: str
    path: Path
    manifest: dict = field(default_factory=dict)

    @property
    def platform(self) -> str | None:
        return self.manifest.get("platform")

    @property
    def params(self) -> dict:
        return self.manifest.get("params") or {}

    @property
    def written(self) -> int | None:
        return (self.manifest.get("counts") or {}).get("written")


def select_runs(interim_dir: Path, only: list[str] | None = None,
                exclude: list[str] | None = None,
                include_test_runs: bool = False) -> tuple[list[RunInfo], list[tuple[str, str]]]:
    """Pilih run yang masuk dataset. Mengembalikan (dipakai, [(run_id, alasan tidak dipakai)])."""
    chosen, skipped = [], []
    only_set, exclude_set = set(only or []), set(exclude or [])
    folders = sorted(p for p in interim_dir.iterdir() if p.is_dir()) if interim_dir.exists() else []
    for folder in folders:
        run_id = folder.name
        manifest_path = folder / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
        if only_set and run_id not in only_set:
            skipped.append((run_id, "tidak disebut di --runs"))
            continue
        if run_id in exclude_set:
            skipped.append((run_id, "disebut di --exclude-runs"))
            continue
        if manifest is None:
            skipped.append((run_id, "tanpa manifest.json"))
            continue
        limit = (manifest.get("params") or {}).get("limit")
        # Run yang disebut eksplisit di --runs tetap dipakai walau run uji.
        if limit and not include_test_runs and run_id not in only_set:
            skipped.append((run_id, f"run uji (--limit {limit})"))
            continue
        chosen.append(RunInfo(run_id, folder, manifest))
    return chosen, skipped


def load_run(run: RunInfo) -> list[dict]:
    records = []
    for batch in sorted(run.path.glob("batch_*.jsonl")):
        for line in batch.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
    return records


# --------------------------------------------------------------- teks

def clean_text(text: str | None) -> str | None:
    """Pembersihan minimal yang aman untuk semua teknik analisis RQ1-RQ3.

    Dilakukan  : normalisasi Unicode (NFKC), URL -> [URL], @mention (termasuk
                 @user_<hash> dari --mask-mentions) -> [USER], spasi dirapikan.
    Tidak      : huruf kecil, hapus tanda baca, hapus emoji, normalisasi slang,
                 stopword, stemming. Sentiment analysis (RQ2) butuh negasi,
                 emoji, dan penekanan seperti "baguuus"; langkah
                 tersebut diputuskan per teknik di tahap analisis, dari kolom
                 `text` asli yang tetap disimpan.
    """
    if not text:
        return None
    cleaned = unicodedata.normalize("NFKC", str(text))
    cleaned = URL_PATTERN.sub("[URL]", cleaned)
    cleaned = MENTION.sub("[USER]", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


def is_mention_only(text: str | None) -> bool:
    """Isinya hanya @mention, boleh disertai emoji atau tanda baca."""
    if not text or not MENTION.search(text):
        return False
    rest = MENTION.sub(" ", unicodedata.normalize("NFKC", text))
    return re.search(r"[^\W_]", rest) is None


def word_count(text_clean: str | None) -> int:
    if not text_clean:
        return 0
    without_tags = re.sub(r"\[(?:USER|URL)\]|#\w+", " ", text_clean)
    return len(WORD_PATTERN.findall(without_tags))


def is_non_indonesian(language: str | None, text_clean: str | None,
                      min_words: int = MIN_WORDS_FOR_LANGUAGE) -> bool:
    if not language:
        return False
    code = str(language).lower().split("-")[0]
    if code in INDONESIAN_LANG or code in AMBIGUOUS_LANG:
        return False
    return word_count(text_clean) >= min_words


def repeat_key(record: dict) -> str:
    """Bentuk teks untuk mendeteksi komentar ganda: huruf kecil, spasi dirapikan."""
    return re.sub(r"\s+", " ", (record.get("text_clean") or "").casefold()).strip()


# ---------------------------------------------------------- pemrosesan

def _blank(value) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def normalize(record: dict) -> dict:
    """Lengkapi kolom skema; ID jadi string; nilai kosong jadi None."""
    out = {key: record.get(key) for key in UNIFIED_FIELDS + ["_scraped_at", "_run_id"]}
    for key in ID_FIELDS:
        out[key] = None if _blank(out[key]) else str(out[key]).strip()
    for key in ("author_hash", "language", "url", "query", "text"):
        if _blank(out[key]):
            out[key] = None
    if not isinstance(out["hashtags"], list):
        out["hashtags"] = extract_hashtags(out["text"])
    if out["item_type"] in NON_POST_TYPES:
        # Tautan komentar/balasan membuka profil penulisnya, sehingga bisa
        # mengenali ulang orang di balik author_hash (minimalisasi data).
        # Tautan aslinya tetap ada di data/interim.
        out["url"] = None
    return out


def process_records(records: list[dict], keywords: dict,
                    min_words: int = MIN_WORDS_FOR_LANGUAGE) -> tuple[list[dict], dict]:
    """Inti tahap processing, tanpa membaca atau menulis berkas.

    Mengembalikan (rows, steps). `steps[platform]` mencatat jumlah record di
    setiap langkah, untuk tabel alur data di report.md.
    """
    steps: dict[str, Counter] = defaultdict(Counter)

    # Gabung + buang yang tidak bisa dipakai.
    usable = []
    for raw in records:
        rec = normalize(raw)
        plat = rec["platform"] if rec["platform"] in VALID_PLATFORMS else "tidak_dikenal"
        steps[plat]["masuk"] += 1
        if rec["item_id"] is None or plat == "tidak_dikenal":
            steps[plat]["dibuang_tanpa_id"] += 1
            continue
        usable.append(rec)

    # Dedup (platform, item_id): simpan versi _scraped_at terbaru.
    latest: dict[tuple[str, str], dict] = {}
    for rec in usable:
        key = (rec["platform"], rec["item_id"])
        if key in latest:
            steps[rec["platform"]]["duplikat"] += 1
            if (rec["_scraped_at"] or "") >= (latest[key]["_scraped_at"] or ""):
                latest[key] = rec
        else:
            latest[key] = rec
    rows = list(latest.values())

    # Tandai per record.
    period = date_ranges(keywords, "periode")
    for rec in rows:
        rec["text_clean"] = clean_text(rec["text"])
        moment = parse_time(rec["created_at"])
        rec["flag_created_at_invalid"] = moment is None
        rec["created_at"] = moment.isoformat().replace("+00:00", "Z") if moment else rec["created_at"]
        rec["flag_out_of_period"] = moment is not None and not in_ranges(moment.isoformat(), period)
        rec["flag_text_missing"] = (rec["text_clean"] is None
                                    or MEDIA_PLACEHOLDER.fullmatch(rec["text_clean"]) is not None)
        rec["flag_mention_only"] = is_mention_only(rec["text"])
        rec["flag_non_indonesian"] = is_non_indonesian(rec["language"], rec["text_clean"], min_words)
        rec["flag_item_type_invalid"] = rec["item_type"] not in VALID_ITEM_TYPES

        author = rec["author_hash"]
        rec["flag_author_not_hashed"] = author is not None and not HASH_PATTERN.fullmatch(author)
        if rec["flag_author_not_hashed"]:
            rec["author_hash"] = None 

        rec["flag_parent_missing"] = rec["item_type"] in ("comment", "reply", "quote") and rec["parent_id"] is None
        rec["flag_conversation_missing"] = rec["platform"] == "x" and rec["conversation_id"] is None

        rec["flag_negative_count"] = False
        for key in COUNT_FIELDS:
            value = rec[key]
            if isinstance(value, (int, float)) and value < 0:
                rec[key] = None  # tidak valid; nol tetap nol (nol != kosong)
                rec["flag_negative_count"] = True

    # Komentar ganda: teks sama dari akun sama di platform yang sama.
    # Hanya comment/reply/quote; caption post yang sama dari satu akun bisa
    # menyertai video berbeda dan tetap dihitung sebagai karya terpisah (RQ1).
    # Kemunculan paling awal dipertahankan. Teks sama dari akun BERBEDA tidak
    # ditandai, karena bisa merupakan pola fan culture yang diteliti.
    for rec in rows:
        rec["flag_repeated_by_author"] = False
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for rec in rows:
        key_text = repeat_key(rec)
        if rec["item_type"] != "post" and rec["author_hash"] and key_text:
            groups[(rec["platform"], rec["author_hash"], key_text)].append(rec)
    for group in groups.values():
        group.sort(key=lambda r: (r["flag_created_at_invalid"], r["created_at"] or "", r["item_id"]))
        for rec in group[1:]:
            rec["flag_repeated_by_author"] = True

    for rec in rows:
        rec["eligible"] = not any(rec[f] for f in EXCLUSION_FLAGS)
        steps[rec["platform"]]["dataset"] += 1
        steps[rec["platform"]]["eligible"] += int(rec["eligible"])

    rows.sort(key=lambda r: (r["platform"], r["created_at"] or "", r["item_id"]))
    return [{key: rec.get(key) for key in OUTPUT_COLUMNS} for rec in rows], {
        plat: dict(counter) for plat, counter in steps.items()}


# ------------------------------------------------------------ simpan

def next_version(processed_dir: Path) -> int:
    numbers = [int(m.group(1)) for p in processed_dir.glob("dataset_v*.metadata.json")
               if (m := re.fullmatch(r"dataset_v(\d+)\.metadata\.json", p.name))]
    return max(numbers, default=0) + 1


def to_frame(rows: list[dict]):
    import pandas as pd

    frame = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    for key in COUNT_FIELDS:
        frame[key] = pd.to_numeric(frame[key], errors="coerce").astype("Int64")
    frame["created_at"] = pd.to_datetime(frame["created_at"], utc=True, errors="coerce", format="ISO8601")
    frame["_scraped_at"] = pd.to_datetime(frame["_scraped_at"], utc=True, errors="coerce", format="ISO8601")
    return frame


def write_outputs(frame, metadata: dict, report: str, processed_dir: Path, stem: str) -> list[Path]:
    processed_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "parquet": processed_dir / f"{stem}.parquet",
        "csv": processed_dir / f"{stem}.csv",
        "metadata": processed_dir / f"{stem}.metadata.json",
        "report": processed_dir / f"{stem}.report.md",
    }
    frame.to_parquet(paths["parquet"], index=False)
    # CSV untuk dibuka di Excel (mis. saat anotasi manual): UTF-8 dengan BOM,
    # daftar hashtag ditulis sebagai teks dipisah spasi.
    csv_frame = frame.copy()
    csv_frame["hashtags"] = csv_frame["hashtags"].map(lambda tags: " ".join(tags) if tags is not None else "")
    csv_frame.to_csv(paths["csv"], index=False, encoding="utf-8-sig")
    paths["metadata"].write_text(json.dumps(metadata, ensure_ascii=False, indent=2, default=str) + "\n",
                                 encoding="utf-8")
    paths["report"].write_text(report, encoding="utf-8")
    return list(paths.values())


# ------------------------------------------------------------ laporan

def _table(headers: list[str], rows: list[list]) -> str:
    def cell(value):
        return "" if value is None else str(value).replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


def render_report(frame, metadata: dict) -> str:
    """Ringkasan dataset. Semua angka dihitung dari `frame`."""
    import pandas as pd

    from src.make_sample import redact

    platforms = [p for p in VALID_PLATFORMS if p in set(frame["platform"])]
    steps = metadata["steps"]
    targets = (metadata["keywords_snapshot"].get("volume_target") or {})
    out = [f"# Laporan {metadata['dataset']}", "",
           f"Dibuat {metadata['created_at']} oleh `src/process.py` (commit {metadata['git_commit']}). "
           f"Periode {metadata['keywords_snapshot']['periode']['mulai']} s/d "
           f"{metadata['keywords_snapshot']['periode']['selesai']} (UTC). "
           "Semua waktu di laporan ini dalam UTC.", ""]

    def noted(value):
        return "tidak tercatat" if value is None else value

    out += ["## 1. Run yang dipakai", ""]
    out.append(_table(
        ["run_id", "platform", "status", "mask_mentions", "written (manifest)", "dibaca"],
        [[r["run_id"], r["platform"], r["status"], noted(r["mask_mentions"]), noted(r["written_manifest"]),
          r["records_read"]] for r in metadata["runs_used"]]))
    if metadata["runs_skipped"]:
        out += ["", "Run yang tidak dipakai:", ""]
        out.append(_table(["run_id", "alasan"], [[r, why] for r, why in metadata["runs_skipped"]]))
    if metadata["warnings"]:
        out += ["", "**Peringatan:**", ""] + [f"- {w}" for w in metadata["warnings"]]

    out += ["", "## 2. Alur jumlah data", "",
            "`eligible` = lolos semua kriteria eksklusi. Target dari `volume_target` di `keywords.yaml`.", ""]
    rows = []
    for plat in platforms:
        s = steps.get(plat, {})
        target = targets.get(plat) or "belum diisi"
        rows.append([plat, s.get("masuk", 0), s.get("dibuang_tanpa_id", 0), s.get("duplikat", 0),
                     s.get("dataset", 0), s.get("eligible", 0), target])
    def total(key):
        return sum(steps.get(p, {}).get(key, 0) for p in platforms)

    rows.append(["**total**", total("masuk"), total("dibuang_tanpa_id"), total("duplikat"),
                 total("dataset"), total("eligible"), ""])
    out.append(_table(["platform", "masuk", "dibuang (tanpa ID)", "duplikat", "dataset", "eligible", "target"], rows))

    out += ["", "## 3. Kriteria eksklusi dan flag", "",
            "Satu record bisa terkena lebih dari satu flag, jadi kolom tidak dijumlahkan.", ""]
    rows = []
    for flag, label in {**EXCLUSION_FLAGS, **INFO_FLAGS}.items():
        kind = "eksklusi" if flag in EXCLUSION_FLAGS else "info"
        rows.append([f"`{flag}`", label, kind] + [int(frame.loc[frame.platform == p, flag].sum()) for p in platforms])
    out.append(_table(["flag", "arti", "jenis"] + platforms, rows))

    out += ["", "## 4. Jenis item", ""]
    rows = []
    for item_type in VALID_ITEM_TYPES:
        cells = []
        for plat in platforms:
            sub = frame[(frame.platform == plat) & (frame.item_type == item_type)]
            cells.append(f"{len(sub)} ({int(sub.eligible.sum())})" if len(sub) else "")
        rows.append([item_type] + cells)
    out.append("Angka: dataset (eligible).\n")
    out.append(_table(["item_type"] + platforms, rows))

    out += ["", "## 5. Sebaran waktu record eligible (per bulan, UTC)", ""]
    eligible = frame[frame.eligible & frame.created_at.notna()]
    months = sorted(eligible.created_at.dt.strftime("%Y-%m").unique())
    rows = [[m] + [int(((eligible.platform == p) & (eligible.created_at.dt.strftime("%Y-%m") == m)).sum())
                   for p in platforms] for m in months]
    out.append(_table(["bulan"] + platforms, rows) if rows else "Belum ada record eligible.")

    out += ["", "## 6. Kode bahasa dari platform (seluruh dataset)", "",
            f"Ditandai bukan Indonesia hanya bila kode di luar {sorted(INDONESIAN_LANG | AMBIGUOUS_LANG)} "
            f"dan teks memuat minimal {metadata['parameters']['min_words_language']} kata.", ""]
    lang = frame.language.fillna("(kosong)")
    codes = lang.value_counts().index.tolist()
    rows = [[c] + [int(((frame.platform == p) & (lang == c)).sum()) for p in platforms] for c in codes]
    out.append(_table(["kode"] + platforms, rows))

    out += ["", "## 7. Kelengkapan kolom (persen kosong)", "",
            "Kosong berbeda dengan nol: like_count = 0 dihitung terisi.", ""]
    rows = []
    for col in ["author_hash", "text", "created_at", "parent_id", "conversation_id", "like_count",
                "reply_count", "share_count", "view_count", "language"]:
        cells = []
        for plat in platforms:
            sub = frame[frame.platform == plat][col]
            cells.append(f"{100 * sub.isna().mean():.0f}%" if len(sub) else "")
        rows.append([col] + cells)
    out.append(_table(["kolom"] + platforms, rows))

    out += ["", "## 8. Relasi balasan", "",
            "Record yang `parent_id`-nya tidak ada di dataset (induk tidak ikut terambil). "
            "Penting untuk menelusuri utas di RQ3.", ""]
    ids = set(zip(frame.platform, frame.item_id))
    rows = []
    for plat in platforms:
        sub = frame[(frame.platform == plat) & frame.parent_id.notna()]
        orphan = sum((plat, pid) not in ids for pid in sub.parent_id)
        rows.append([plat, len(sub), orphan])
    out.append(_table(["platform", "punya parent_id", "induk tidak ada di dataset"], rows))

    out += ["", "## 9. Konsentrasi komentar per video", "",
            "Komentar (comment/reply) yang eligible dikelompokkan per `conversation_id` "
            "(video). Konsentrasi tinggi berarti sampel didominasi beberapa video; "
            "penting untuk membaca bias sampling dan memilih sampel anotasi.", ""]
    rows = []
    for plat in platforms:
        sub = frame[(frame.platform == plat) & frame.eligible & (frame.item_type != "post")]
        per_video = sub.groupby("conversation_id").size().sort_values(ascending=False)
        total = int(per_video.sum())
        if not total:
            continue
        top10pct = max(1, round(len(per_video) * 0.10))
        rows.append([plat, len(per_video), total, int(per_video.median()), int(per_video.iloc[0]),
                     f"{100 * per_video.iloc[:5].sum() / total:.0f}%",
                     f"{100 * per_video.iloc[:top10pct].sum() / total:.0f}%"])
    out.append(_table(["platform", "video berkomentar", "komentar eligible", "median/video",
                       "terbanyak", "porsi 5 video teratas", "porsi 10% video teratas"], rows)
               if rows else "Belum ada komentar eligible.")

    out += ["", "## 10. Contoh baris eligible", "",
            "Teks disamarkan seperti `data/sample/` (@mention diganti, dipotong 80 karakter).", ""]
    rows = []
    for plat in platforms:
        sub = frame[(frame.platform == plat) & frame.eligible].head(3)
        for _, r in sub.iterrows():
            rows.append([plat, r.item_type, redact(r.text, 80),
                         r.created_at.strftime("%Y-%m-%d") if pd.notna(r.created_at) else "",
                         r.like_count, " ".join(r.hashtags or [])])
    out.append(_table(["platform", "item_type", "text", "created_at", "like_count", "hashtags"], rows)
               if rows else "Belum ada record eligible.")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------- main

def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Processing interim -> processed")
    parser.add_argument("--runs", nargs="+", default=None, help="Hanya pakai run_id ini")
    parser.add_argument("--exclude-runs", nargs="+", default=None, help="Jangan pakai run_id ini")
    parser.add_argument("--include-test-runs", action="store_true",
                        help="Ikutkan run uji (yang memakai --limit)")
    parser.add_argument("--min-words-language", type=int, default=MIN_WORDS_FOR_LANGUAGE,
                        help=f"Minimal kata untuk menandai bukan bahasa Indonesia (bawaan {MIN_WORDS_FOR_LANGUAGE})")
    parser.add_argument("--data-dir", type=Path, default=None,
                        help="Folder data (bawaan DATA_DIR di .env, yaitu data/)")
    return parser.parse_args(argv)


def run(args, logger, run_id: str) -> int:
    settings = Settings.from_env()
    data_dir = args.data_dir if args.data_dir else settings.data_dir
    interim_dir, processed_dir = data_dir / "interim", data_dir / "processed"
    keywords = load_keywords()

    runs, skipped = select_runs(interim_dir, args.runs, args.exclude_runs, args.include_test_runs)
    for run_id, why in skipped:
        logger.info("Run %s tidak dipakai: %s", run_id, why)
    if not runs:
        logger.error("Tidak ada run yang bisa dipakai di %s.", interim_dir)
        return 1

    records, runs_used, warnings = [], [], []
    for info in runs:
        recs = load_run(info)
        records.extend(recs)
        runs_used.append({
            "run_id": info.run_id, "platform": info.platform,
            "status": info.manifest.get("status"), "started_at": info.manifest.get("started_at"),
            "git_commit": (info.manifest.get("environment") or {}).get("git_commit"),
            "mask_mentions": info.params.get("mask_mentions"), "params": info.params,
            "written_manifest": info.written, "records_read": len(recs),
        })
        logger.info("Run %s (%s, %s): %d record", info.run_id, info.platform,
                    info.manifest.get("status"), len(recs))
        if info.written is not None and info.written != len(recs):
            warnings.append(f"{info.run_id}: manifest mencatat {info.written} record, terbaca {len(recs)}.")
        if info.manifest.get("status") != "completed":
            warnings.append(f"{info.run_id}: status run `{info.manifest.get('status')}`.")
    mask_values = {r["mask_mentions"] for r in runs_used}
    if len(mask_values) > 1:
        warnings.append("Setelan --mask-mentions berbeda antar run; text_clean tetap menyamakan "
                        "semua mention menjadi [USER], tetapi kolom `text` tidak seragam.")
    for warning in warnings:
        logger.warning(warning)

    rows, steps = process_records(records, keywords, args.min_words_language)
    frame = to_frame(rows)

    version = next_version(processed_dir)
    stem = f"dataset_v{version:02d}"
    period = date_ranges(keywords, "periode")[0]

    import pandas as pd
    import pyarrow

    metadata = {
        "dataset": stem,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "description": "Dataset terpadu (platform: " + ", ".join(sorted(steps)) + ") setelah penggabungan "
                       "run, dedup, dan penandaan kriteria eksklusi. Record tidak dihapus; filter kolom "
                       "`eligible`. Kolom url dikosongkan untuk comment/reply/quote.",
        "script": "src/process.py",
        "git_commit": _git_commit(),
        "process_run_id": run_id,
        "period": [period[0].isoformat(), period[1].isoformat()],
        "parameters": {
            "dedup_key": ["platform", "item_id"],
            "dedup_keep": "versi dengan _scraped_at terbaru",
            "min_words_language": args.min_words_language,
            "indonesian_lang": sorted(INDONESIAN_LANG),
            "ambiguous_lang_not_flagged": sorted(AMBIGUOUS_LANG),
            "include_test_runs": args.include_test_runs,
            "runs": args.runs, "exclude_runs": args.exclude_runs,
        },
        "environment": {"python": platform_module.python_version(),
                        "pandas": pd.__version__, "pyarrow": pyarrow.__version__},
        "runs_used": runs_used,
        "runs_skipped": skipped,
        "warnings": warnings,
        "steps": steps,
        "flags": {f: {p: int(frame.loc[frame.platform == p, f].sum()) for p in steps if p in VALID_PLATFORMS}
                  for f in ALL_FLAGS},
        "keywords_snapshot": keywords,
        "columns": OUTPUT_COLUMNS,
    }
    report = render_report(frame, metadata)
    paths = write_outputs(frame, metadata, report, processed_dir, stem)

    for plat, s in steps.items():
        logger.info("%-10s masuk %5d | tanpa ID %3d | duplikat %4d | dataset %5d | eligible %5d",
                    plat, s.get("masuk", 0), s.get("dibuang_tanpa_id", 0), s.get("duplikat", 0),
                    s.get("dataset", 0), s.get("eligible", 0))
    for path in paths:
        logger.info("Ditulis: %s", path.relative_to(ROOT) if path.is_relative_to(ROOT) else path)
    return 0


def main(argv=None) -> int:
    args = parse_args(argv)
    run_id = new_run_id("process")
    logger = setup_logging(run_id)
    return run(args, logger, run_id)


if __name__ == "__main__":
    sys.exit(main())

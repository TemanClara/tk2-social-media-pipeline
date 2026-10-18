"""Titik masuk untuk menjalankan scraping.

Contoh:
    python -m src.run_scrape --platform x --dry-run      # cek konfigurasi saja
    python -m src.run_scrape --platform x --limit 20     # uji coba kecil
    python -m src.run_scrape --platform tiktok           # run penuh
    python -m src.run_scrape --platform instagram --with-accounts --comment-pages 20
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys

from src.common.config import Settings, keywords_path, load_keywords
from src.common.logging_setup import new_run_id, setup_logging
from src.common.manifest import RunManifest
from src.common.storage import BatchWriter, RawArchive, SeenStore
from src.scrapers._common import TIKTOK_SORTS, X_BUDGETS, X_SORTS, RunOptions, date_ranges
from src.scrapers.instagram_scraper import InstagramScraper
from src.scrapers.tiktok_scraper import TikTokScraper
from src.scrapers.x_scraper import XScraper, build_query

SCRAPERS = {
    "x": XScraper,
    "tiktok": TikTokScraper,
    "instagram": InstagramScraper,
}

# Kredensial yang wajib ada di .env per platform. TikTok dan Instagram
# diakses tanpa login, jadi cukup salt untuk pseudonimisasi.
REQUIRED_SECRETS = {
    "x": ["X_BEARER_TOKEN", "PSEUDONYM_SALT"],
    "tiktok": ["PSEUDONYM_SALT"],
    "instagram": ["PSEUDONYM_SALT"],
}
REQUIRED_MODULES = {"tiktok": ["curl_cffi", "marshmallow"], "instagram": ["curl_cffi", "marshmallow"]}


def parse_args() -> argparse.Namespace:
    defaults = RunOptions()
    parser = argparse.ArgumentParser(description="Pengumpulan data TK-2")
    parser.add_argument("--platform", required=True, choices=sorted(SCRAPERS))
    parser.add_argument("--limit", type=int, default=None,
                        help="Batas jumlah record, untuk uji coba")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--max-pages", type=int, default=defaults.max_pages,
                        help=f"Halaman hasil per kueri/hashtag/akun (bawaan {defaults.max_pages})")
    parser.add_argument("--comment-pages", type=int, default=defaults.comment_pages,
                        help=f"Halaman komentar per unggahan, TikTok/Instagram (bawaan {defaults.comment_pages})")
    parser.add_argument("--with-accounts", action="store_true",
                        help="Ikut ambil unggahan dari akun_target (TikTok/Instagram)")
    parser.add_argument("--window", choices=["periode", "peristiwa"], default=defaults.window,
                        help="Rentang waktu: seluruh periode, atau jendela per peristiwa_pemicu")
    parser.add_argument("--x-sort", choices=X_SORTS, default=defaults.x_sort,
                        help=f"Urutan pencarian X: relevancy (paling relevan) atau recency (terbaru). Bawaan {defaults.x_sort}")
    parser.add_argument("--tiktok-sort", choices=TIKTOK_SORTS, default=defaults.tiktok_sort,
                        help=f"Urutan pencarian kata kunci TikTok: likes (paling banyak like) atau relevance. Bawaan {defaults.tiktok_sort}")
    parser.add_argument("--tiktok-replies", type=int, default=defaults.tiktok_replies,
                        help="Halaman balasan per komentar TikTok (~20 balasan/halaman). Bawaan 0 = tidak diambil")
    parser.add_argument("--x-budget", choices=X_BUDGETS, default=defaults.x_budget,
                        help="Pembagian X_MAX_POSTS_READ antar rentang waktu: rata (dibagi per rentang) "
                             f"atau bersama (dipakai berurutan). Bawaan {defaults.x_budget}")
    parser.add_argument("--mask-mentions", action="store_true",
                        help="Samarkan @username di dalam teks menjadi @user_<hash> saat scraping")
    parser.add_argument("--dry-run", action="store_true",
                        help="Periksa konfigurasi dan kredensial tanpa mengambil data")
    return parser.parse_args()


def dry_run(args, settings: Settings, keywords: dict, logger) -> int:
    """Periksa kesiapan tanpa menyentuh jaringan."""
    platform = args.platform
    problems = 0
    logger.info("Mode dry-run: tidak ada data yang diambil.")
    logger.info("Parameter dibaca dari %s", keywords_path())
    logger.info("Periode: %s sampai %s",
                keywords["periode"]["mulai"], keywords["periode"]["selesai"])
    for start, end in date_ranges(keywords, args.window):
        logger.info("Rentang (%s): %s s/d %s", args.window, start.date(), end.date())
    logger.info("Kata kunci: %d | Hashtag: %d",
                len(keywords.get("kata_kunci", [])), len(keywords.get("hashtag", [])))
    if platform == "x":
        logger.info("Kueri X: %s", build_query(keywords))
        logger.info("Batas baca X_MAX_POSTS_READ: %s", os.getenv("X_MAX_POSTS_READ", "2000 (bawaan)"))

    akun = keywords.get("akun_target", {}).get(platform, [])
    logger.info("Akun target %s: %d%s", platform, len(akun),
                "" if args.with_accounts or platform == "x" else " (tidak dipakai tanpa --with-accounts)")
    if args.with_accounts and not akun:
        logger.warning("--with-accounts dipakai tapi akun_target.%s masih kosong — menunggu C1.", platform)

    for name in REQUIRED_SECRETS[platform]:
        if os.getenv(name):
            logger.info("%s: terisi", name)  # nilainya sengaja tidak ditampilkan
        else:
            logger.error("%s belum diisi di .env", name)
            problems += 1
    for module in REQUIRED_MODULES.get(platform, []):
        if importlib.util.find_spec(module) is None:
            logger.error("Modul %s belum terpasang. Jalankan: make setup", module)
            problems += 1

    logger.info("Jeda antar permintaan: %.1f detik | Retry maksimum: %d",
                settings.request_delay_seconds, settings.max_retries)
    logger.info("Halaman per sumber: %d | Halaman komentar: %d", args.max_pages, args.comment_pages)
    if platform == "x":
        logger.info("Urutan pencarian X: %s | Pembagian batas baca: %s", args.x_sort, args.x_budget)
    logger.info("Samarkan @username di teks: %s", "ya" if args.mask_mentions else "tidak")
    if platform == "tiktok":
        logger.info("Urutan pencarian TikTok: %s | Halaman balasan per komentar: %d",
                    args.tiktok_sort, args.tiktok_replies)
    for folder in (settings.raw_dir, settings.interim_dir, settings.processed_dir):
        folder.mkdir(parents=True, exist_ok=True)
    logger.info("Folder data siap di %s", settings.data_dir)
    if problems:
        logger.error("Dry-run menemukan %d masalah.", problems)
        return 1
    logger.info("Dry-run lolos.")
    return 0


def main() -> int:
    args = parse_args()
    run_id = new_run_id(args.platform)
    logger = setup_logging(run_id)
    settings = Settings.from_env()
    keywords = load_keywords()

    if args.dry_run:
        return dry_run(args, settings, keywords, logger)

    logger.info("Mulai run %s", run_id)
    options = RunOptions(max_pages=args.max_pages, comment_pages=args.comment_pages,
                         with_accounts=args.with_accounts, window=args.window,
                         x_sort=args.x_sort, tiktok_sort=args.tiktok_sort,
                         tiktok_replies=args.tiktok_replies, x_budget=args.x_budget,
                         mask_mentions=args.mask_mentions)

    manifest = RunManifest(
        run_id=run_id,
        platform=args.platform,
        params={"limit": args.limit, "batch_size": args.batch_size,
                "max_pages": options.max_pages, "comment_pages": options.comment_pages,
                "with_accounts": options.with_accounts, "window": options.window,
                "mask_mentions": options.mask_mentions,
                **({"x_sort": options.x_sort, "x_budget": options.x_budget} if args.platform == "x" else {}),
                **({"tiktok_sort": options.tiktok_sort, "tiktok_replies": options.tiktok_replies}
                   if args.platform == "tiktok" else {}),
                "request_delay_seconds": settings.request_delay_seconds,
                "max_retries": settings.max_retries},
        keywords_snapshot=keywords,
    )
    manifest_path = settings.interim_dir / run_id / "manifest.json"

    archive = RawArchive(settings.raw_dir, run_id)
    scraper = SCRAPERS[args.platform](settings, keywords, logger, archive=archive)
    scraper.options = options
    seen = SeenStore(settings.raw_dir / f"_seen_{args.platform}.txt")
    status = "completed"

    try:
        with BatchWriter(settings.interim_dir, run_id, args.batch_size) as writer:
            try:
                for record in scraper.collect(limit=args.limit):
                    manifest.bump("fetched")
                    item_id = record.get("item_id")
                    if item_id and item_id in seen:
                        manifest.bump("duplicates")
                        continue
                    writer.write(record)
                    manifest.bump("written")
                    manifest.bump(f"written_{record.get('item_type')}")
                    if item_id:
                        seen.add(item_id)
                    if args.limit and writer.total >= args.limit:
                        logger.info("Batas %d record tercapai.", args.limit)
                        break
            except KeyboardInterrupt:
                status = "interrupted"
                logger.warning("Dihentikan manual. Data yang sudah tertulis tetap tersimpan.")
            except Exception:
                # Kegagalan per permintaan sudah ditangani di scraper; yang
                # sampai ke sini adalah error tak terduga (bug, konfigurasi).
                status = "failed"
                manifest.bump("errors")
                logger.exception("Run berhenti karena error tak terduga.")
            logger.info("Selesai. %d record tersimpan, %d duplikat dilewati.",
                        writer.total, manifest.counts["duplicates"])
    finally:
        seen.close()
        for key, value in getattr(scraper, "stats", {}).items():
            manifest.bump(key, value)
        manifest.counts["raw_pages"] = archive.total
        manifest.finish(status)
        manifest.save(manifest_path)
        logger.info("Statistik: %s", manifest.counts)
        logger.info("Manifest run disimpan di %s", manifest_path)

    return {"completed": 0, "interrupted": 130, "failed": 1}[status]


if __name__ == "__main__":
    sys.exit(main())

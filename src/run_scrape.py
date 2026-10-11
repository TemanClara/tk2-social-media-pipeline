"""Titik masuk untuk menjalankan scraping.

Contoh:
    python -m src.run_scrape --platform x --dry-run      # cek konfigurasi saja
    python -m src.run_scrape --platform x --limit 50     # uji coba kecil
    python -m src.run_scrape --platform tiktok           # run penuh
"""

from __future__ import annotations

import argparse
import sys

from src.common.config import Settings, keywords_path, load_keywords
from src.common.logging_setup import new_run_id, setup_logging
from src.common.manifest import RunManifest
from src.common.storage import BatchWriter, RawArchive, SeenStore
from src.scrapers.instagram_scraper import InstagramScraper
from src.scrapers.tiktok_scraper import TikTokScraper
from src.scrapers.x_scraper import XScraper

SCRAPERS = {
    "x": XScraper,
    "tiktok": TikTokScraper,
    "instagram": InstagramScraper,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pengumpulan data TK-2")
    parser.add_argument("--platform", required=True, choices=sorted(SCRAPERS))
    parser.add_argument("--limit", type=int, default=None,
                        help="Batas jumlah record, untuk uji coba")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true",
                        help="Periksa konfigurasi dan kredensial tanpa mengambil data")
    return parser.parse_args()


def dry_run(platform: str, settings: Settings, keywords: dict, logger) -> int:
    """Periksa kesiapan tanpa menyentuh jaringan."""
    logger.info("Mode dry-run: tidak ada data yang diambil.")
    logger.info("Parameter dibaca dari %s", keywords_path())
    logger.info("Periode: %s sampai %s",
                keywords["periode"]["mulai"], keywords["periode"]["selesai"])
    logger.info("Kata kunci: %d | Hashtag: %d",
                len(keywords.get("kata_kunci", [])), len(keywords.get("hashtag", [])))

    akun = keywords.get("akun_target", {}).get(platform, [])
    logger.info("Akun target %s: %d", platform, len(akun))
    if not akun and platform == "instagram":
        logger.warning("Daftar akun Instagram masih kosong — menunggu C1.")

    logger.info("Jeda antar permintaan: %.1f detik | Retry maksimum: %d",
                settings.request_delay_seconds, settings.max_retries)
    for folder in (settings.raw_dir, settings.interim_dir, settings.processed_dir):
        folder.mkdir(parents=True, exist_ok=True)
    logger.info("Folder data siap di %s", settings.data_dir)
    return 0


def main() -> int:
    args = parse_args()
    run_id = new_run_id(args.platform)
    logger = setup_logging(run_id)
    settings = Settings.from_env()
    keywords = load_keywords()

    if args.dry_run:
        return dry_run(args.platform, settings, keywords, logger)

    logger.info("Mulai run %s", run_id)

    manifest = RunManifest(
        run_id=run_id,
        platform=args.platform,
        params={"limit": args.limit, "batch_size": args.batch_size,
                "request_delay_seconds": settings.request_delay_seconds,
                "max_retries": settings.max_retries},
        keywords_snapshot=keywords,
    )
    manifest_path = settings.interim_dir / run_id / "manifest.json"

    archive = RawArchive(settings.raw_dir, run_id)
    scraper = SCRAPERS[args.platform](settings, keywords, logger, archive=archive)
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
                    if item_id:
                        seen.add(item_id)
                    if args.limit and writer.total >= args.limit:
                        logger.info("Batas %d record tercapai.", args.limit)
                        break
            except KeyboardInterrupt:
                status = "interrupted"
                logger.warning("Dihentikan manual. Data yang sudah tertulis tetap tersimpan.")
            except NotImplementedError as exc:
                status = "failed"
                manifest.bump("errors")
                logger.error("%s", exc)
            logger.info("Selesai. %d record tersimpan, %d duplikat dilewati.",
                        writer.total, manifest.counts["duplicates"])
    finally:
        seen.close()
        manifest.counts["raw_pages"] = archive.total
        manifest.finish(status)
        manifest.save(manifest_path)
        logger.info("Manifest run disimpan di %s", manifest_path)

    return {"completed": 0, "interrupted": 130, "failed": 1}[status]


if __name__ == "__main__":
    sys.exit(main())

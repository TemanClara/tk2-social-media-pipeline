"""Scraper Instagram — menjawab RQ2 (distribusi sentimen).

Yang perlu terambil: unggahan akun berita dan akun fanbase beserta seluruh
komentarnya. Kolom komentar pada satu unggahan yang sama kerap memuat
kekaguman dan kritik berdampingan, dan perbandingan itulah yang diukur pada
RQ2, sehingga komentar pada satu unggahan sebaiknya diambil utuh, bukan
sebagian.

STATUS: kerangka.
"""

from __future__ import annotations

from typing import Iterator

from src.scrapers.base import BaseScraper


class InstagramScraper(BaseScraper):
    platform = "instagram"

    def collect(self, limit: int | None = None) -> Iterator[dict]:
        accounts = self.keywords.get("akun_target", {}).get("instagram", [])
        if not accounts:
            self.logger.warning(
                "Daftar akun Instagram masih kosong di config/keywords.yaml "
                "(menunggu C1)."
            )
        for account in accounts:
            self.logger.info("Instagram: mengambil unggahan @%s", account)
            # TODO 0 — simpan respons asli: self.archive.save(payload)
            # TODO 1 — daftar unggahan akun dalam rentang periode.
            # TODO 2 — komentar tiap unggahan, parent_id = id unggahan.
            # TODO 3 — hanya akun publik; akun privat dilewati (lihat C6).
            raise NotImplementedError("Isi collect() untuk Instagram.")
            yield  # pragma: no cover

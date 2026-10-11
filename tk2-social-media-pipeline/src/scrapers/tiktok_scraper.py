"""Scraper TikTok — menjawab RQ1 (praktik fan culture).

Yang perlu terambil: video per hashtag/kata kunci beserta caption, metadata,
dan komentarnya. Konten fan-edit, kompilasi, dan video reaksi adalah sasaran
utamanya, jadi caption dan hashtag ikut disimpan sebagai penanda praktik
produksi konten turunan.

Catatan: seluruh teknik analitik berbasis teks, sehingga isi video tidak
diproses. Yang disimpan adalah caption, hashtag, metadata, dan komentar.
(Lihat keputusan terbuka nomor 5 pada lembar Acuan TK-1.)

STATUS: kerangka.
"""

from __future__ import annotations

from typing import Iterator

from src.scrapers.base import BaseScraper


class TikTokScraper(BaseScraper):
    platform = "tiktok"

    def collect(self, limit: int | None = None) -> Iterator[dict]:
        hashtags = self.keywords.get("hashtag", [])
        self.logger.info("TikTok: %d hashtag akan ditelusuri", len(hashtags))

        for tag in hashtags:
            self.logger.info("TikTok: menelusuri #%s", tag)
            # TODO 0 — simpan respons asli: self.archive.save(payload)
            # TODO 1 — daftar video per hashtag (id, caption, metadata, tanggal).
            # TODO 2 — komentar tiap video, dengan parent_id = id video.
            # TODO 3 — pagination lewat cursor + jeda antar permintaan.
            raise NotImplementedError("Isi collect() untuk TikTok.")
            yield  # pragma: no cover

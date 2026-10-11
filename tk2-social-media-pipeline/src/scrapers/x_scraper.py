"""Scraper X — menjawab RQ3 (pola respons penggemar terhadap kritik).

Yang perlu terambil: post opini, balasan, quote-tweet, serta conversation_id
dan ID post yang dibalas. Relasi balasan inilah yang membuat X menjadi
satu-satunya platform yang bisa menjawab RQ3, jadi kolom parent_id dan
conversation_id tidak boleh kosong.

STATUS: kerangka. Isi collect() setelah keputusan API vs scraping
dicatat di docs/decisions.md.
"""

from __future__ import annotations

from typing import Iterator

from src.scrapers.base import BaseScraper


class XScraper(BaseScraper):
    platform = "x"

    def collect(self, limit: int | None = None) -> Iterator[dict]:
        queries = self.keywords.get("kata_kunci", []) + [
            f"#{tag}" for tag in self.keywords.get("hashtag", [])
        ]
        self.logger.info("X: %d kueri akan dijalankan", len(queries))

        for query in queries:
            self.logger.info("X: mencari '%s'", query)
            # TODO 0 — simpan respons asli: self.archive.save(payload)
            # TODO 1 — pencarian post berdasarkan kueri + rentang tanggal.
            # TODO 2 — untuk tiap post, ambil balasan dan quote-tweet-nya.
            # TODO 3 — pagination lewat cursor; berhenti saat cursor habis
            #          atau saat `limit` tercapai.
            # Contoh bentuk record yang diharapkan:
            #
            # yield self.to_unified(
            #     item_type="reply",
            #     item_id=item["id"],
            #     parent_id=item["in_reply_to_status_id"],
            #     conversation_id=item["conversation_id"],
            #     author_hash=hash_username(item["user"]["screen_name"]),
            #     text=item["full_text"],
            #     created_at=item["created_at"],
            #     like_count=item["favorite_count"],
            #     reply_count=item["reply_count"],
            #     url=f"https://x.com/i/status/{item['id']}",
            #     query=query,
            # )
            raise NotImplementedError("Isi collect() untuk X.")
            yield  # pragma: no cover

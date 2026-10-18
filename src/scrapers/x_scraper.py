"""Scraper X — menjawab RQ3 (pola respons penggemar terhadap kritik).

Yang perlu terambil: post opini, balasan, quote-tweet, serta conversation_id
dan ID post yang dibalas. Relasi balasan inilah yang membuat X menjadi
satu-satunya platform yang bisa menjawab RQ3, jadi kolom parent_id dan
conversation_id tidak boleh kosong.

Cara akses: X API v2 resmi (bayar per pemakaian, Bearer Token dari X
Developer Console di .env sebagai X_BEARER_TOKEN).

    1. Pencarian arsip penuh  GET /2/tweets/search/all
       Satu kueri gabungan per rentang waktu:
       ("Teddy Indra Wijaya" OR "Mayor Teddy" OR ... OR #mayorteddy) -is:retweet lang:id
       Retweet dibuang karena teksnya terpotong dan metriknya milik post asli.
       Urutan diatur --x-sort: "relevancy" (bawaan) menyebar hasil di sepanjang
       rentang; "recency" mengambil yang terbaru dulu, sehingga dengan batas
       baca hasilnya menumpuk di akhir rentang (diuji 18 Okt 2026).
    2. Balasan tiap percakapan  GET /2/tweets/search/all
       dengan kueri conversation_id:<id> -is:retweet, start_time = waktu post.
       Hanya untuk post yang reply_count > 0. Memakai urutan bawaan X, tidak
       mengikuti --x-sort.
    3. Quote-tweet  GET /2/tweets/:id/quote_tweets
       Hanya untuk post yang quote_count > 0.

Pengaman biaya (tiap post yang dibaca ditagih):
    X_MAX_POSTS_READ di .env   batas total post yang dibaca per run (bawaan 2000)
    MAX_REPLIES / MAX_QUOTES   batas per percakapan
    --limit                    juga memperkecil ukuran halaman saat uji coba
Parameter `expansions` sengaja tidak dipakai supaya objek pengguna tidak ikut
ditagih. Akibatnya username tidak diketahui, dan author_hash dibuat dari
author_id (ID numerik akun), yang tetap konsisten walau akun ganti username.
"""

from __future__ import annotations

import os
import re
from typing import Iterator

from src.common.anonymize import hash_username
from src.common.config import get_secret
from src.common.http import get_with_retry, make_session
from src.scrapers._common import ScraperRuntime, date_ranges
from src.scrapers.base import BaseScraper

API = "https://api.x.com/2"
TWEET_FIELDS = ["author_id", "created_at", "conversation_id", "public_metrics",
                "referenced_tweets", "lang", "note_tweet"]
MAX_REPLIES = 100   # per percakapan
MAX_QUOTES = 50     # per post
DEFAULT_MAX_POSTS_READ = 2000


def build_query(keywords: dict) -> str:
    terms = [f'"{kw}"' for kw in keywords.get("kata_kunci", [])]
    terms += [f"#{tag.lstrip('#')}" for tag in keywords.get("hashtag", [])]
    if not terms:
        raise ValueError("kata_kunci dan hashtag kosong di config/keywords.yaml")
    lang = keywords.get("bahasa", {}).get("utama")
    query = f"({' OR '.join(terms)}) -is:retweet"
    if lang and not keywords.get("bahasa", {}).get("sertakan_non_indonesia", False):
        query += f" lang:{lang}"
    return query


def matched_terms(text: str, keywords: dict) -> str | None:
    """Kata kunci/hashtag mana yang muncul di teks, untuk kolom `query`."""
    lowered = (text or "").lower()
    found = [kw for kw in keywords.get("kata_kunci", []) if kw.lower() in lowered]
    found += [f"#{tag}" for tag in keywords.get("hashtag", [])
              if re.search(rf"#{re.escape(tag.lstrip('#'))}\b", lowered, re.I)]
    return "; ".join(found) or None


def _rfc3339(moment) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


class XScraper(ScraperRuntime, BaseScraper):
    platform = "x"

    def __init__(self, *args, session=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._session = session
        self._fields = list(TWEET_FIELDS)
        self._fields_confirmed = False

    @property
    def session(self):
        if self._session is None:
            token = get_secret("X_BEARER_TOKEN")
            self._session = make_session({"Authorization": f"Bearer {token}"})
        return self._session

    def collect(self, limit: int | None = None) -> Iterator[dict]:
        self.budget = int(os.getenv("X_MAX_POSTS_READ", DEFAULT_MAX_POSTS_READ))
        self.page_size = max(10, min(100, limit)) if limit else 100
        self._done_conversations: set[str] = set()
        query = build_query(self.keywords)
        ranges = date_ranges(self.keywords, self.options.window)
        self.logger.info("X: kueri %s", query)
        self.logger.info("X: %d rentang waktu, batas baca %d post, urutan %s",
                         len(ranges), self.budget, self.options.x_sort)

        for start, end in ranges:
            self.logger.info("X: mencari %s s/d %s", start.date(), end.date())
            params = {"query": query, "start_time": _rfc3339(start), "end_time": _rfc3339(end),
                      "sort_order": self.options.x_sort}
            for post in self._paged("/tweets/search/all", params, label="x_search",
                                    max_pages=self.options.max_pages, max_items=None):
                terms = matched_terms(self._text(post), self.keywords)
                yield self._record(post, terms)
                yield from self._thread(post, terms)

    # --- percakapan -------------------------------------------------------

    def _thread(self, post: dict, terms: str | None) -> Iterator[dict]:
        metrics = post.get("public_metrics") or {}
        conversation = post.get("conversation_id")
        if metrics.get("reply_count") and conversation and conversation not in self._done_conversations:
            self._done_conversations.add(conversation)
            params = {"query": f"conversation_id:{conversation} -is:retweet",
                      "start_time": post["created_at"]}
            for reply in self._paged("/tweets/search/all", params, label="x_replies",
                                     max_pages=None, max_items=MAX_REPLIES):
                yield self._record(reply, terms)
        if metrics.get("quote_count"):
            for quote in self._paged(f"/tweets/{post['id']}/quote_tweets", {}, label="x_quotes",
                                     max_pages=None, max_items=MAX_QUOTES, token_param="pagination_token"):
                yield self._record(quote, terms, quoted_id=post["id"])

    # --- permintaan -------------------------------------------------------

    def _paged(self, path, params, *, label, max_pages, max_items,
               token_param="next_token") -> Iterator[dict]:
        token, page, taken = None, 0, 0
        while max_pages is None or page < max_pages:
            if self.budget <= 0:
                self.stats["budget_exhausted"] += 1
                self.logger.warning("X: batas X_MAX_POSTS_READ tercapai, berhenti mengambil.")
                return
            size = min(self.page_size, self.budget, (max_items - taken) if max_items else 100)
            size = max(10, size)  # batas bawah max_results di kedua endpoint
            payload = self._get(path, {**params, "max_results": size,
                                       **({token_param: token} if token else {})}, label)
            if payload is None:
                return
            page += 1
            data = payload.get("data") or []
            self.budget -= len(data)
            self.stats["posts_read"] += len(data)
            for item in data:
                yield item
                taken += 1
                if max_items and taken >= max_items:
                    return
            token = (payload.get("meta") or {}).get("next_token")
            if not token:
                return

    def _get(self, path, params, label) -> dict | None:
        params = {**params, "tweet.fields": ",".join(self._fields)}
        response = get_with_retry(self.session, API + path, params=params,
                                  max_retries=self.settings.max_retries,
                                  delay_seconds=self.settings.request_delay_seconds)
        if response is None and "note_tweet" in self._fields and not self._fields_confirmed:
            # Nama field teks panjang belum terverifikasi di akses ini. Bila
            # permintaan pertama ditolak, ulangi sekali tanpa field itu (teks
            # post panjang bisa terpotong).
            self._fields.remove("note_tweet")
            self.logger.warning("X: tweet.fields note_tweet ditolak, diulang tanpa note_tweet.")
            return self._get(path, {k: v for k, v in params.items() if k != "tweet.fields"}, label)
        if response is None:
            self.stats["errors"] += 1
            return None
        self._fields_confirmed = True
        payload = response.json()
        if self.archive:
            self.archive.save(payload, label=label)
        for error in payload.get("errors") or []:
            # error per item (mis. post dihapus) tidak menggagalkan halaman
            self.logger.warning("X: %s", error.get("detail") or error)
        return payload

    # --- pemetaan ---------------------------------------------------------

    @staticmethod
    def _text(item: dict) -> str | None:
        return (item.get("note_tweet") or {}).get("text") or item.get("text")

    def _record(self, item: dict, terms: str | None, quoted_id: str | None = None) -> dict:
        refs = {ref["type"]: ref["id"] for ref in item.get("referenced_tweets") or []}
        if "replied_to" in refs:
            item_type, parent = "reply", refs["replied_to"]
        elif "quoted" in refs or quoted_id:
            item_type, parent = "quote", refs.get("quoted", quoted_id)
        else:
            item_type, parent = "post", None
        metrics = item.get("public_metrics") or {}
        author = item.get("author_id")
        return self.to_unified(
            item_type=item_type,
            item_id=str(item["id"]),
            parent_id=str(parent) if parent else None,
            conversation_id=item.get("conversation_id"),
            author_hash=hash_username(str(author)) if author else None,
            text=self._text(item),
            created_at=item.get("created_at"),
            like_count=metrics.get("like_count"),
            reply_count=metrics.get("reply_count"),
            share_count=metrics.get("retweet_count"),
            url=f"https://x.com/i/status/{item['id']}",
            query=terms,
        )

"""Tes scraper X dengan session HTTP tiruan (tanpa jaringan, tanpa biaya)."""

from __future__ import annotations

import os
import unittest
from unittest import mock

from src.common.anonymize import hash_username
from src.scrapers._common import RunOptions
from src.scrapers.base import UNIFIED_FIELDS
from src.scrapers.x_scraper import XScraper, build_query, matched_terms
from tests.helpers import KEYWORDS, make


def tweet(tid, text="Mayor Teddy keren", author="111", conv=None, replies=0, quotes=0, refs=None):
    return {"id": tid, "text": text, "author_id": author, "conversation_id": conv or tid,
            "created_at": "2025-02-01T10:00:00.000Z", "referenced_tweets": refs or [],
            "public_metrics": {"like_count": 5, "reply_count": replies, "quote_count": quotes,
                               "retweet_count": 2}}


class FakeResponse:
    def __init__(self, status, payload=None, headers=None):
        self.status_code = status
        self._payload = payload or {}
        self.headers = headers or {}
        self.text = str(payload)

    def json(self):
        return self._payload


class FakeSession:
    """Menjawab berdasarkan path dan kueri; mencatat semua permintaan."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        for matches, answer in self.routes:
            if matches(url, params or {}):
                result = answer(url, params or {}) if callable(answer) else answer
                return result if isinstance(result, FakeResponse) else FakeResponse(200, result)
        return FakeResponse(200, {"meta": {"result_count": 0}})


def is_search(url, params):
    return url.endswith("/tweets/search/all") and not params["query"].startswith("conversation_id:")


def is_replies(url, params):
    return url.endswith("/tweets/search/all") and params["query"].startswith("conversation_id:")


def is_quotes(url, params):
    return url.endswith("/quote_tweets")


class XScraperTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ, {"X_MAX_POSTS_READ": "2000"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_scraper(self, session, limit=None, options=None):
        scraper, archive = make(XScraper, session=session, options=options)
        return scraper, archive, list(scraper.collect(limit=limit))

    def test_query_combines_terms_and_drops_retweets(self):
        self.assertEqual(build_query(KEYWORDS), '("Mayor Teddy" OR #mayorteddy) -is:retweet lang:id')

    def test_search_replies_and_quotes_are_linked(self):
        session = FakeSession([
            (is_search, {"data": [tweet("1", replies=1, quotes=1)], "meta": {}}),
            (is_replies, {"data": [tweet("2", conv="1", author="222",
                                          refs=[{"type": "replied_to", "id": "1"}])], "meta": {}}),
            (is_quotes, {"data": [tweet("3", author="333", refs=[{"type": "quoted", "id": "1"}])], "meta": {}}),
        ])
        _, archive, records = self.run_scraper(session)

        self.assertEqual([(r["item_type"], r["item_id"], r["parent_id"]) for r in records],
                         [("post", "1", None), ("reply", "2", "1"), ("quote", "3", "1")])
        for record in records:
            self.assertEqual(set(record), set(UNIFIED_FIELDS))
            self.assertEqual(record["url"], f"https://x.com/i/status/{record['item_id']}")
        self.assertEqual(records[1]["conversation_id"], "1")
        self.assertEqual(records[0]["author_hash"], hash_username("111"))
        self.assertEqual(records[0]["share_count"], 2)
        self.assertEqual(records[0]["query"], "Mayor Teddy")
        self.assertEqual([label for label, _ in archive.saved], ["x_search", "x_replies", "x_quotes"])

        reply_params = [p for u, p in session.calls if is_replies(u, p)][0]
        self.assertEqual(reply_params["query"], "conversation_id:1 -is:retweet")
        self.assertEqual(reply_params["start_time"], "2025-02-01T10:00:00.000Z")

    def test_no_thread_requests_when_counts_are_zero(self):
        session = FakeSession([(is_search, {"data": [tweet("1")], "meta": {}})])
        self.run_scraper(session)
        self.assertEqual(len(session.calls), 1)

    def test_search_uses_period_and_no_expansions(self):
        session = FakeSession([(is_search, {"data": [], "meta": {}})])
        self.run_scraper(session)
        params = session.calls[0][1]
        self.assertEqual(params["start_time"], "2024-10-01T00:00:00Z")
        self.assertEqual(params["end_time"], "2026-10-01T00:00:00Z")
        self.assertNotIn("expansions", params)
        self.assertIn("conversation_id", params["tweet.fields"])

    def test_search_sort_defaults_to_relevancy_and_follows_option(self):
        session = FakeSession([(is_search, {"data": [tweet("1", replies=1)], "meta": {}})])
        self.run_scraper(session, options=RunOptions())
        search = [p for u, p in session.calls if is_search(u, p)][0]
        replies = [p for u, p in session.calls if is_replies(u, p)][0]
        self.assertEqual(search["sort_order"], "relevancy")
        self.assertNotIn("sort_order", replies)  # balasan pakai urutan bawaan X

        session = FakeSession([(is_search, {"data": [], "meta": {}})])
        self.run_scraper(session, options=RunOptions(x_sort="recency"))
        self.assertEqual(session.calls[0][1]["sort_order"], "recency")

    def three_windows_session(self):
        """Peristiwa pertama sangat ramai (selalu ada halaman berikutnya), dua lainnya sepi."""
        def search(url, params):
            size = int(params["max_results"])
            if params["start_time"].startswith("2024-10-20"):
                n = int(params.get("next_token", "0"))
                return {"data": [tweet(f"a{n}-{i}") for i in range(size)], "meta": {"next_token": str(n + 1)}}
            prefix = params["start_time"][:7]
            return {"data": [tweet(f"{prefix}-{i}") for i in range(5)], "meta": {}}
        return FakeSession([(is_search, search)])

    def keywords_with_three_events(self):
        return {**KEYWORDS, "peristiwa_pemicu": [
            {"nama": "a", "tanggal": "2024-10-20", "jendela_hari": 14},
            {"nama": "b", "tanggal": "2025-02-25", "jendela_hari": 14},
            {"nama": "c", "tanggal": "2026-05-13", "jendela_hari": 14}]}

    def test_budget_split_evenly_gives_every_event_a_share(self):
        with mock.patch.dict(os.environ, {"X_MAX_POSTS_READ": "300"}):
            session = self.three_windows_session()
            scraper, _ = make(XScraper, session=session,
                              options=RunOptions(window="peristiwa", max_pages=50, x_budget="rata"))
            scraper.keywords = self.keywords_with_three_events()
            records = list(scraper.collect())
        months = [r["item_id"][:7] for r in records if not r["item_id"].startswith("a")]
        self.assertEqual(sorted(set(months)), ["2025-02", "2026-05"])
        self.assertEqual(scraper.stats["posts_read_2024-10-20"], 100)
        self.assertEqual(scraper.stats["posts_read_2025-02-25"], 5)
        self.assertEqual(scraper.stats["posts_read_2026-05-13"], 5)

    def test_unused_share_rolls_over_to_later_events(self):
        with mock.patch.dict(os.environ, {"X_MAX_POSTS_READ": "300"}):
            session = self.three_windows_session()
            scraper, _ = make(XScraper, session=session,
                              options=RunOptions(window="peristiwa", max_pages=50, x_budget="rata"))
            scraper.keywords = {**self.keywords_with_three_events(), "peristiwa_pemicu": list(reversed(
                self.keywords_with_three_events()["peristiwa_pemicu"]))}
            list(scraper.collect())
        # dua peristiwa sepi dulu (5 + 5), sisanya (290) untuk peristiwa ramai
        self.assertEqual(scraper.stats["posts_read_2024-10-20"], 290)

    def test_shared_budget_lets_first_event_take_everything(self):
        with mock.patch.dict(os.environ, {"X_MAX_POSTS_READ": "300"}):
            session = self.three_windows_session()
            scraper, _ = make(XScraper, session=session,
                              options=RunOptions(window="peristiwa", max_pages=50, x_budget="bersama"))
            scraper.keywords = self.keywords_with_three_events()
            records = list(scraper.collect())
        self.assertTrue(all(r["item_id"].startswith("a") for r in records))
        self.assertEqual(scraper.stats["posts_read_2024-10-20"], 300)

    def test_new_columns_and_mention_masking(self):
        post = tweet("1", text="@akun_asli Mayor Teddy #MayorTeddy #fyp")
        post["public_metrics"]["impression_count"] = 1234
        post["lang"] = "in"
        session = FakeSession([(is_search, {"data": [post], "meta": {}})])
        _, _, plain = self.run_scraper(session)
        self.assertEqual(plain[0]["view_count"], 1234)
        self.assertEqual(plain[0]["language"], "in")
        self.assertEqual(plain[0]["hashtags"], ["mayorteddy", "fyp"])
        self.assertIn("@akun_asli", plain[0]["text"])

        session = FakeSession([(is_search, {"data": [post], "meta": {}})])
        _, _, masked = self.run_scraper(session, options=RunOptions(mask_mentions=True))
        self.assertNotIn("akun_asli", masked[0]["text"])
        self.assertIn(f"@user_{hash_username('akun_asli')}", masked[0]["text"])

    def test_event_windows_make_one_search_per_event(self):
        session = FakeSession([(is_search, {"data": [], "meta": {}})])
        self.run_scraper(session, options=RunOptions(window="peristiwa"))
        params = session.calls[0][1]
        self.assertEqual((params["start_time"], params["end_time"]), ("2024-10-20T00:00:00Z", "2024-11-04T00:00:00Z"))

    def test_pagination_follows_next_token_up_to_max_pages(self):
        def search(url, params):
            n = int(params.get("next_token", "0"))
            return {"data": [tweet(f"p{n}")], "meta": {"next_token": str(n + 1)}}

        session = FakeSession([(is_search, search)])
        _, _, records = self.run_scraper(session, options=RunOptions(max_pages=3))
        self.assertEqual([r["item_id"] for r in records], ["p0", "p1", "p2"])

    def test_read_budget_stops_requests(self):
        with mock.patch.dict(os.environ, {"X_MAX_POSTS_READ": "15"}):
            def search(url, params):
                n = int(params.get("next_token", "0"))
                data = [tweet(f"p{n}-{i}") for i in range(int(params["max_results"]))]
                return {"data": data, "meta": {"next_token": str(n + 1)}}

            session = FakeSession([(is_search, search)])
            scraper, _, records = self.run_scraper(session, limit=10, options=RunOptions(max_pages=10))
        self.assertEqual([p["max_results"] for _, p in session.calls], [10, 10])
        self.assertEqual(scraper.stats["budget_exhausted"], 1)

    def test_rejected_note_tweet_field_is_retried_without_it(self):
        def search(url, params):
            if "note_tweet" in params["tweet.fields"]:
                return FakeResponse(400, {"errors": [{"message": "invalid field"}]})
            return {"data": [tweet("1")], "meta": {}}

        session = FakeSession([(is_search, search)])
        _, _, records = self.run_scraper(session)
        self.assertEqual(len(records), 1)
        self.assertNotIn("note_tweet", session.calls[-1][1]["tweet.fields"])

    def test_long_post_text_comes_from_note_tweet(self):
        long = tweet("1", text="awal...")
        long["note_tweet"] = {"text": "awal dan teks lengkap Mayor Teddy"}
        session = FakeSession([(is_search, {"data": [long], "meta": {}})])
        _, _, records = self.run_scraper(session)
        self.assertEqual(records[0]["text"], "awal dan teks lengkap Mayor Teddy")

    def test_rate_limit_waits_then_retries(self):
        answers = [FakeResponse(429, {}, {"x-rate-limit-reset": "0"}), {"data": [tweet("1")], "meta": {}}]
        session = FakeSession([(is_search, lambda u, p: answers.pop(0))])
        scraper, _ = make(XScraper, session=session)
        scraper.settings = scraper.settings.__class__(request_delay_seconds=0.0, max_retries=2,
                                                      data_dir=scraper.settings.data_dir)
        with mock.patch("src.common.http.time.sleep") as sleep:
            records = list(scraper.collect())
        self.assertEqual(len(records), 1)
        self.assertTrue(sleep.called)

    def test_failed_search_counts_error_without_crashing(self):
        session = FakeSession([(is_search, FakeResponse(403, {"title": "Forbidden"}))])
        scraper, _, records = self.run_scraper(session)
        self.assertEqual(records, [])
        self.assertGreaterEqual(scraper.stats["errors"], 1)

    def test_matched_terms(self):
        self.assertEqual(matched_terms("halo #MayorTeddy dan mayor teddy", KEYWORDS), "Mayor Teddy; #mayorteddy")
        self.assertIsNone(matched_terms("tidak relevan", KEYWORDS))


if __name__ == "__main__":
    unittest.main()

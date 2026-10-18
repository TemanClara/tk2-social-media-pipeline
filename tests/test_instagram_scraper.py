"""Tes scraper Instagram dengan library tiruan (tanpa jaringan)."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from src.common.anonymize import hash_username
from src.scrapers._common import RunOptions
from src.scrapers.base import UNIFIED_FIELDS
from src.scrapers.instagram_scraper import InstagramScraper
from tests.helpers import make, pages


def full_post(code, published="2025-02-14T11:18:13Z", comments=5, owner="pemilik_asli", pinned=False):
    return {"id": f"id{code}", "code": code, "link": f"https://www.instagram.com/reel/{code}/",
            "caption": f"caption {code}", "published_at": published, "is_pinned": pinned,
            "owner": {"username": owner}, "stats": {"like_count": 7, "comment_count": comments}}


def search_post(code):
    """Bentuk hasil pencarian: tanpa tanggal dan tanpa like/komentar."""
    return {"id": f"id{code}", "code": code, "caption": f"caption {code}",
            "owner": {"username": "pemilik_asli"},
            "stats": {"like_count": None, "comment_count": None, "play_count": 100}}


def comment(cid, parent=None, user="komentator_asli"):
    return {"id": cid, "text": f"komentar {cid}", "created_at": "2025-02-15T00:00:00Z", "like_count": 2,
            "reply_count": 1, "user": {"username": user}, "parent_comment_id": parent}


def library(keyword=None, hashtag=None, user=None, details=None, comments=None):
    empty = pages({"posts": []})
    return SimpleNamespace(keyword_posts=keyword or empty, hashtag_posts=hashtag or empty,
                           user_posts=user or empty, details=details or (lambda code: full_post(code)),
                           comments=comments or pages({"comments": []}))


class InstagramScraperTest(unittest.TestCase):
    def test_search_results_are_completed_with_details(self):
        detail_calls = []

        def details(code):
            detail_calls.append(code)
            return full_post(code)

        lib = library(keyword=pages({"posts": [search_post("A")]}), details=details,
                      comments=pages({"comments": [comment("c1"), comment("c2", parent="c1")]}))
        scraper, archive = make(InstagramScraper, library=lib)
        records = list(scraper.collect())

        self.assertEqual(detail_calls, ["A"])
        self.assertEqual([r["item_type"] for r in records], ["post", "comment", "reply"])
        post, top, reply = records
        self.assertEqual(post["created_at"], "2025-02-14T11:18:13Z")
        self.assertEqual(post["like_count"], 7)
        self.assertEqual(post["query"], "kata_kunci:Mayor Teddy")
        self.assertEqual(top["parent_id"], "idA")
        self.assertEqual(reply["parent_id"], "c1")
        self.assertEqual(top["url"], "https://www.instagram.com/p/A/c/c1/")
        for record in records:
            self.assertEqual(set(record), set(UNIFIED_FIELDS))
            self.assertEqual(record["conversation_id"], "idA")
        self.assertIn("instagram_details", [label for label, _ in archive.saved])

    def test_usernames_are_hashed_never_stored(self):
        lib = library(keyword=pages({"posts": [search_post("A")]}),
                      comments=pages({"comments": [comment("c1")]}))
        scraper, _ = make(InstagramScraper, library=lib)
        records = list(scraper.collect())
        self.assertEqual(records[0]["author_hash"], hash_username("pemilik_asli"))
        self.assertEqual(records[1]["author_hash"], hash_username("komentator_asli"))
        for record in records:
            for field, value in record.items():
                self.assertNotIn("asli", str(value).lower(), f"username bocor di kolom {field}")

    def test_keyword_and_hashtag_are_default_accounts_optional(self):
        user = pages({"posts": [full_post("U", comments=0)]})
        lib = library(keyword=pages({"posts": [search_post("K")]}), hashtag=pages({"posts": [search_post("H")]}),
                      details=lambda code: full_post(code, comments=0), user=user)
        scraper, _ = make(InstagramScraper, library=lib)
        self.assertEqual([r["query"] for r in scraper.collect()], ["kata_kunci:Mayor Teddy", "hashtag:mayorteddy"])
        self.assertEqual(user.calls, [])

        scraper, _ = make(InstagramScraper, library=lib,
                          options=RunOptions(max_pages=2, comment_pages=1, with_accounts=True))
        self.assertEqual([r["query"] for r in scraper.collect()][-1], "akun:akunberita")

    def test_keywords_are_sent_lowercase_but_labelled_as_written(self):
        keyword = pages({"posts": [search_post("A")]})
        scraper, _ = make(InstagramScraper, library=library(keyword=keyword,
                                                            details=lambda code: full_post(code, comments=0)))
        records = list(scraper.collect())
        self.assertEqual(keyword.calls, [("mayor teddy", None)])
        self.assertEqual(records[0]["query"], "kata_kunci:Mayor Teddy")

    def test_private_account_is_skipped(self):
        user = pages({"posts": [], "is_private": True})
        scraper, _ = make(InstagramScraper, library=library(user=user),
                          options=RunOptions(max_pages=2, comment_pages=1, with_accounts=True))
        self.assertEqual(list(scraper.collect()), [])
        self.assertEqual(scraper.stats["private_accounts_skipped"], 1)

    def test_comments_paginate_and_cap_is_recorded(self):
        comments = pages(*[{"comments": [comment(f"c{i}")]} for i in range(1, 6)])
        lib = library(keyword=pages({"posts": [search_post("A")]}), comments=comments)
        scraper, _ = make(InstagramScraper, library=lib, options=RunOptions(max_pages=1, comment_pages=3))
        records = list(scraper.collect())
        self.assertEqual([r["item_id"] for r in records[1:]], ["c1", "c2", "c3"])
        self.assertEqual(scraper.stats["comment_page_cap_reached"], 1)

    def test_out_of_period_posts_are_skipped(self):
        lib = library(keyword=pages({"posts": [search_post("lama"), search_post("baru")]}),
                      details=lambda code: full_post(code, comments=0,
                                                     published="2023-01-01T00:00:00Z" if code == "lama"
                                                     else "2025-01-01T00:00:00Z"))
        scraper, _ = make(InstagramScraper, library=lib)
        self.assertEqual([r["item_id"] for r in scraper.collect()], ["idbaru"])
        self.assertEqual(scraper.stats["out_of_period"], 1)

    def test_failed_detail_skips_only_that_post(self):
        def details(code):
            if code == "rusak":
                raise RuntimeError("diblokir")
            return full_post(code, comments=0)

        lib = library(keyword=pages({"posts": [search_post("rusak"), search_post("ok")]}), details=details)
        scraper, _ = make(InstagramScraper, library=lib)
        self.assertEqual([r["item_id"] for r in scraper.collect()], ["idok"])
        self.assertEqual(scraper.stats["errors"], 1)


if __name__ == "__main__":
    unittest.main()

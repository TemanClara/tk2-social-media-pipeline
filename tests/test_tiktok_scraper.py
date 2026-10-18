"""Tes scraper TikTok dengan library tiruan (tanpa jaringan)."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from src.common.anonymize import hash_username
from src.scrapers._common import RunOptions
from src.scrapers.base import UNIFIED_FIELDS
from src.scrapers.tiktok_scraper import TikTokScraper
from tests.helpers import make, pages


def video(vid, created="2025-03-01T10:00:00Z", comments=2, user="kreator", pinned=False):
    return {"id": vid, "link": f"https://www.tiktok.com/@{user}/video/{vid}", "description": f"caption {vid}",
            "created_at": created, "is_pinned": pinned, "author": {"username": user},
            "stats": {"like_count": 10, "comment_count": comments, "share_count": 3}}


def comment(cid, parent=None, user="penonton"):
    return {"id": cid, "text": f"komentar {cid}", "created_at": "2025-03-02T00:00:00Z", "like_count": 1,
            "reply_count": 0, "parent_comment_id": parent, "user": {"username": user},
            "link": f"https://www.tiktok.com/@/video/x?comment_id={cid}"}


def library(search=None, hashtag=None, user=None, comments=None, replies=None):
    empty = pages({"videos": []})
    return SimpleNamespace(search_videos=search or empty, hashtag_videos=hashtag or empty,
                           user_videos=user or empty, comments=comments or pages({"comments": []}),
                           replies=replies or (lambda video_id, comment_id, cursor: {"replies": []}))


class TikTokScraperTest(unittest.TestCase):
    def test_video_and_comments_follow_unified_schema(self):
        lib = library(search=pages({"videos": [video("v1")]}),
                      comments=pages({"comments": [comment("c1"), comment("c2", parent="c1")]}))
        scraper, _ = make(TikTokScraper, library=lib)
        records = list(scraper.collect())

        self.assertEqual([r["item_type"] for r in records], ["post", "comment", "reply"])
        for record in records:
            self.assertEqual(set(record), set(UNIFIED_FIELDS))
            self.assertEqual(record["platform"], "tiktok")
            self.assertEqual(record["conversation_id"], "v1")
            self.assertEqual(record["query"], "kata_kunci:Mayor Teddy")
        post, top, reply = records
        self.assertIsNone(post["parent_id"])
        self.assertEqual(top["parent_id"], "v1")
        self.assertEqual(reply["parent_id"], "c1")
        self.assertEqual(post["reply_count"], 2)
        self.assertEqual(post["share_count"], 3)

    def test_view_count_language_and_hashtags(self):
        v = dict(video("v1"), description="Keren #MayorTeddy #fyp", language="id")
        v["stats"] = dict(v["stats"], play_count=999)
        lib = library(search=pages({"videos": [v]}),
                      comments=pages({"comments": [dict(comment("c1"), language="en")]}))
        scraper, _ = make(TikTokScraper, library=lib)
        post, top = list(scraper.collect())
        self.assertEqual((post["view_count"], post["language"], post["hashtags"]), (999, "id", ["mayorteddy", "fyp"]))
        self.assertEqual((top["view_count"], top["language"], top["hashtags"]), (None, "en", []))

    def test_mask_mentions_option(self):
        lib = library(search=pages({"videos": [video("v1", comments=1)]}),
                      comments=pages({"comments": [dict(comment("c1"), text="@teman_asli lihat ini")]}))
        scraper, _ = make(TikTokScraper, library=lib, options=RunOptions(mask_mentions=True))
        records = list(scraper.collect())
        self.assertEqual(records[1]["text"], f"@user_{hash_username('teman_asli')} lihat ini")

    def test_usernames_are_hashed_never_stored(self):
        lib = library(search=pages({"videos": [video("v1", user="Kreator.Asli")]}),
                      comments=pages({"comments": [comment("c1", user="penonton_asli")]}))
        scraper, _ = make(TikTokScraper, library=lib)
        records = list(scraper.collect())
        self.assertEqual(records[0]["author_hash"], hash_username("Kreator.Asli"))
        self.assertEqual(records[1]["author_hash"], hash_username("penonton_asli"))
        for record in records:
            for field, value in record.items():
                self.assertNotIn("asli", str(value).lower(), f"username bocor di kolom {field}")

    def test_paginates_until_has_more_false(self):
        search = pages({"videos": [video("v1", comments=0)]}, {"videos": [video("v2", comments=0)]})
        scraper, archive = make(TikTokScraper, library=library(search=search))
        records = list(scraper.collect())
        self.assertEqual([r["item_id"] for r in records], ["v1", "v2"])
        self.assertEqual(search.calls, [("Mayor Teddy", None), ("Mayor Teddy", "2")])
        self.assertEqual(len(archive.saved), 3)  # 2 halaman pencarian + 1 halaman hashtag (kosong)

    def test_max_pages_and_comment_pages_are_respected(self):
        search = pages(*[{"videos": [video(f"v{i}")]} for i in range(1, 6)])
        comments = pages(*[{"comments": [comment(f"c{i}")]} for i in range(1, 6)])
        scraper, _ = make(TikTokScraper, library=library(search=search, comments=comments),
                          options=RunOptions(max_pages=2, comment_pages=1))
        records = list(scraper.collect())
        self.assertEqual([r["item_id"] for r in records if r["item_type"] == "post"], ["v1", "v2"])
        self.assertEqual(sum(r["item_type"] == "comment" for r in records), 2)

    def test_videos_outside_period_are_skipped_with_their_comments(self):
        lib = library(search=pages({"videos": [video("lama", created="2023-05-01T00:00:00Z"), video("baru")]}),
                      comments=pages({"comments": [comment("c1")]}))
        scraper, _ = make(TikTokScraper, library=lib)
        records = list(scraper.collect())
        self.assertEqual([r["item_id"] for r in records], ["baru", "c1"])
        self.assertEqual(scraper.stats["out_of_period"], 1)

    def test_same_video_from_two_sources_is_fetched_once(self):
        lib = library(search=pages({"videos": [video("v1")]}), hashtag=pages({"videos": [video("v1")]}),
                      comments=pages({"comments": [comment("c1")]}))
        scraper, _ = make(TikTokScraper, library=lib)
        self.assertEqual([r["item_id"] for r in scraper.collect()], ["v1", "c1"])

    def test_failed_request_is_logged_and_run_continues(self):
        def broken(value, cursor):
            raise RuntimeError("diblokir")

        lib = library(search=broken, hashtag=pages({"videos": [video("v2", comments=0)]}))
        scraper, _ = make(TikTokScraper, library=lib)
        self.assertEqual([r["item_id"] for r in scraper.collect()], ["v2"])
        self.assertEqual(scraper.stats["errors"], 1)

    def test_search_sort_defaults_to_likes_and_follows_option(self):
        search = pages({"videos": []})
        scraper, _ = make(TikTokScraper, library=library(search=search), options=RunOptions())
        list(scraper.collect())
        self.assertEqual(search.kwargs, [{"sort": "likes"}])

        search = pages({"videos": []})
        scraper, _ = make(TikTokScraper, library=library(search=search),
                          options=RunOptions(tiktok_sort="relevance"))
        list(scraper.collect())
        self.assertEqual(search.kwargs, [{"sort": "relevance"}])

    def test_replies_are_off_by_default(self):
        calls = []

        def replies(video_id, comment_id, cursor):
            calls.append(comment_id)
            return {"replies": [comment("r1")]}

        with_replies = dict(comment("c1"), reply_count=3)
        lib = library(search=pages({"videos": [video("v1")]}), comments=pages({"comments": [with_replies]}),
                      replies=replies)
        scraper, _ = make(TikTokScraper, library=lib)
        self.assertEqual([r["item_id"] for r in scraper.collect()], ["v1", "c1"])
        self.assertEqual(calls, [])

    def test_replies_fetched_only_for_comments_with_replies(self):
        calls = []

        def replies(video_id, comment_id, cursor):
            calls.append((video_id, comment_id, cursor))
            if cursor is None:
                return {"replies": [comment("r1")], "next_cursor": "20", "has_more": True}
            return {"replies": [comment("r2")], "next_cursor": None, "has_more": False}

        lib = library(search=pages({"videos": [video("v1")]}),
                      comments=pages({"comments": [dict(comment("c1"), reply_count=2), comment("c2")]}),
                      replies=replies)
        scraper, archive = make(TikTokScraper, library=lib,
                                options=RunOptions(max_pages=1, comment_pages=1, tiktok_replies=5))
        records = list(scraper.collect())

        self.assertEqual([(r["item_type"], r["item_id"], r["parent_id"]) for r in records],
                         [("post", "v1", None), ("comment", "c1", "v1"), ("reply", "r1", "c1"),
                          ("reply", "r2", "c1"), ("comment", "c2", "v1")])
        self.assertEqual(calls, [("v1", "c1", None), ("v1", "c1", "20")])
        self.assertTrue(all(r["conversation_id"] == "v1" for r in records))
        self.assertIn("tiktok_replies", [label for label, _ in archive.saved])

    def test_reply_page_cap_is_recorded(self):
        def replies(video_id, comment_id, cursor):
            return {"replies": [comment(f"r{cursor}")], "next_cursor": "x", "has_more": True}

        lib = library(search=pages({"videos": [video("v1")]}),
                      comments=pages({"comments": [dict(comment("c1"), reply_count=9)]}), replies=replies)
        scraper, _ = make(TikTokScraper, library=lib,
                          options=RunOptions(max_pages=1, comment_pages=1, tiktok_replies=1))
        self.assertEqual(sum(r["item_type"] == "reply" for r in scraper.collect()), 1)
        self.assertEqual(scraper.stats["reply_page_cap_reached"], 1)

    def test_accounts_only_with_flag_and_stop_at_old_videos(self):
        user = pages({"videos": [video("pin", created="2020-01-01T00:00:00Z", pinned=True, comments=0),
                                 video("u1", comments=0), video("lama", created="2024-01-01T00:00:00Z")]},
                     {"videos": [video("tidak_diambil")]})
        scraper, _ = make(TikTokScraper, library=library(user=user))
        self.assertEqual(list(scraper.collect()), [])

        scraper, _ = make(TikTokScraper, library=library(user=user),
                          options=RunOptions(max_pages=3, comment_pages=1, with_accounts=True))
        records = list(scraper.collect())
        self.assertEqual([r["item_id"] for r in records], ["u1"])
        self.assertEqual(records[0]["query"], "akun:akunfan")
        self.assertEqual(len(user.calls), 1)  # berhenti, tidak membuka halaman 2


if __name__ == "__main__":
    unittest.main()

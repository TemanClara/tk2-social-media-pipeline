"""Tes tahap processing (src/process.py). Tanpa jaringan, tanpa data asli."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from tests.helpers import KEYWORDS, LOGGER  # noqa: F401  (helpers juga memasang salt tes)

from src.common.anonymize import hash_username
from src.process import (clean_text, is_mention_only, is_non_indonesian, process_records,
                         select_runs)

HAS_PANDAS = all(importlib.util.find_spec(m) for m in ("pandas", "pyarrow"))


def rec(item_id, *, platform="tiktok", item_type="comment", text="komentar biasa saja",
        author="akun_a", created_at="2025-03-01T10:00:00Z", parent_id="v1",
        conversation_id="v1", language="id", scraped="2026-10-19T02:00:00+00:00",
        run_id="tiktok_20261019_090000", **extra):
    record = {
        "platform": platform, "item_type": item_type, "item_id": item_id,
        "parent_id": None if item_type == "post" else parent_id,
        "conversation_id": conversation_id,
        "author_hash": hash_username(author) if author else None,
        "text": text, "created_at": created_at,
        "like_count": 0, "reply_count": 0, "share_count": None, "view_count": None,
        "hashtags": [], "language": language, "url": None, "query": "kata_kunci:Mayor Teddy",
        "_scraped_at": scraped, "_run_id": run_id,
    }
    record.update(extra)
    return record


def by_id(rows):
    return {r["item_id"]: r for r in rows}


class CleanTextTest(unittest.TestCase):
    def test_url_and_mentions_replaced_rest_kept(self):
        self.assertEqual(clean_text("@budi_01 KEREN bgt!!! 😍 https://t.co/x"),
                         "[USER] KEREN bgt!!! 😍 [URL]")

    def test_masked_mention_also_replaced(self):
        self.assertEqual(clean_text("halo @user_3f9a1c0b7d2e4a68 setuju"), "halo [USER] setuju")

    def test_email_not_treated_as_mention(self):
        self.assertEqual(clean_text("kirim ke a@b.com"), "kirim ke a@b.com")

    def test_empty_becomes_none(self):
        self.assertIsNone(clean_text("   "))


class MentionOnlyTest(unittest.TestCase):
    def test_only_mentions(self):
        self.assertTrue(is_mention_only("@budi @sari"))
        self.assertTrue(is_mention_only("@user_3f9a1c0b7d2e4a68 😂😂"))

    def test_mention_with_words_is_not_only(self):
        self.assertFalse(is_mention_only("@budi lihat ini deh"))
        self.assertFalse(is_mention_only("@budi #mayorteddy"))
        self.assertFalse(is_mention_only("tanpa mention"))


class LanguageTest(unittest.TestCase):
    def test_long_foreign_text_flagged(self):
        self.assertTrue(is_non_indonesian("en", "This edit is really well made"))

    def test_short_text_not_flagged(self):
        # TikTok sering salah deteksi teks pendek (mis. "tr" untuk "wkwk").
        self.assertFalse(is_non_indonesian("tr", "wkwkwk"))

    def test_indonesian_and_ambiguous_codes_not_flagged(self):
        for code in ("id", "in", "ms", "tl", "jv", "und", "zxx", None):
            self.assertFalse(is_non_indonesian(code, "aku suka banget sama konten ini"), code)


class ProcessRecordsTest(unittest.TestCase):
    def test_duplicate_across_runs_keeps_latest_scrape(self):
        old = rec("c1", like_count=5, scraped="2026-10-19T02:00:00+00:00")
        new = rec("c1", like_count=9, scraped="2026-10-20T02:00:00+00:00", run_id="tiktok_20261020_090000")
        rows, steps = process_records([new, old], KEYWORDS)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["like_count"], 9)
        self.assertEqual(steps["tiktok"]["duplikat"], 1)

    def test_same_id_on_different_platforms_is_not_duplicate(self):
        rows, _ = process_records([rec("1"), rec("1", platform="instagram")], KEYWORDS)
        self.assertEqual(len(rows), 2)

    def test_record_without_id_is_dropped_and_counted(self):
        rows, steps = process_records([rec(None), rec("c2")], KEYWORDS)
        self.assertEqual([r["item_id"] for r in rows], ["c2"])
        self.assertEqual(steps["tiktok"]["dibuang_tanpa_id"], 1)

    def test_repeated_comment_same_author_flagged_after_first(self):
        rows = by_id(process_records([
            rec("c2", text="Semoga amanah 🙏", created_at="2025-03-02T10:00:00Z"),
            rec("c1", text="semoga  amanah 🙏", created_at="2025-03-01T10:00:00Z", parent_id="v9"),
            rec("c3", text="Semoga amanah 🙏", author="akun_b"),
        ], KEYWORDS)[0])
        self.assertFalse(rows["c1"]["flag_repeated_by_author"])   # paling awal
        self.assertTrue(rows["c2"]["flag_repeated_by_author"])
        self.assertFalse(rows["c3"]["flag_repeated_by_author"])   # akun berbeda
        self.assertFalse(rows["c2"]["eligible"])

    def test_same_caption_on_two_posts_not_flagged(self):
        rows = process_records([
            rec("v1", item_type="post", text="#mayorteddy #fyp"),
            rec("v2", item_type="post", text="#mayorteddy #fyp"),
        ], KEYWORDS)[0]
        self.assertFalse(any(r["flag_repeated_by_author"] for r in rows))

    def test_out_of_period_comment_flagged(self):
        rows = by_id(process_records([
            rec("in", created_at="2026-09-30T23:59:00Z"),
            rec("out", created_at="2026-10-01T00:00:01Z"),
        ], KEYWORDS)[0])
        self.assertFalse(rows["in"]["flag_out_of_period"])
        self.assertTrue(rows["out"]["flag_out_of_period"])

    def test_invalid_time_flagged_not_out_of_period(self):
        row = process_records([rec("c1", created_at="kemarin sore")], KEYWORDS)[0][0]
        self.assertTrue(row["flag_created_at_invalid"])
        self.assertFalse(row["flag_out_of_period"])
        self.assertFalse(row["eligible"])

    def test_unhashed_author_is_removed(self):
        raw = rec("c1")
        raw["author_hash"] = "username_asli"
        row = process_records([raw], KEYWORDS)[0][0]
        self.assertTrue(row["flag_author_not_hashed"])
        self.assertIsNone(row["author_hash"])

    def test_zero_kept_negative_cleared(self):
        rows = by_id(process_records([rec("a", like_count=0), rec("b", like_count=-3, author="akun_b")],
                                     KEYWORDS)[0])
        self.assertEqual(rows["a"]["like_count"], 0)
        self.assertIsNone(rows["b"]["like_count"])
        self.assertTrue(rows["b"]["flag_negative_count"])
        self.assertTrue(rows["b"]["eligible"])   # flag info saja

    def test_x_reply_without_conversation_is_info_flag_only(self):
        row = process_records([rec("1", platform="x", item_type="reply", conversation_id=None)], KEYWORDS)[0][0]
        self.assertTrue(row["flag_conversation_missing"])
        self.assertTrue(row["eligible"])

    def test_media_placeholder_counts_as_no_text(self):
        rows = by_id(process_records([rec("img", text="[Foto]"), rec("emoji", text="😍😍😍")], KEYWORDS)[0])
        self.assertTrue(rows["img"]["flag_text_missing"])
        self.assertFalse(rows["emoji"]["flag_text_missing"])   # emoji membawa makna (Modul 6)

    def test_missing_hashtags_column_filled_from_text(self):
        raw = rec("v1", item_type="post", text="Kompilasi #MayorTeddy #fyp")
        del raw["hashtags"]
        row = process_records([raw], KEYWORDS)[0][0]
        self.assertEqual(row["hashtags"], ["mayorteddy", "fyp"])

    def test_eligible_when_no_exclusion_flag(self):
        rows = by_id(process_records([
            rec("ok"), rec("empty", text=""), rec("tag", text="@budi"),
            rec("en", text="This edit is really well made", language="en"),
        ], KEYWORDS)[0])
        self.assertTrue(rows["ok"]["eligible"])
        self.assertTrue(rows["empty"]["flag_text_missing"])
        self.assertTrue(rows["tag"]["flag_mention_only"])
        self.assertTrue(rows["en"]["flag_non_indonesian"])
        self.assertEqual([k for k, r in rows.items() if r["eligible"]], ["ok"])


def write_run(interim: Path, run_id: str, records: list[dict], *, limit=None, manifest=True):
    folder = interim / run_id
    folder.mkdir(parents=True)
    (folder / "batch_0001.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    if manifest:
        (folder / "manifest.json").write_text(json.dumps({
            "run_id": run_id, "platform": records[0]["platform"], "status": "completed",
            "params": {"limit": limit, "mask_mentions": False},
            "counts": {"written": len(records)}, "environment": {"git_commit": "abc1234"},
        }), encoding="utf-8")


class SelectRunsTest(unittest.TestCase):
    def test_test_runs_and_runs_without_manifest_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            interim = Path(tmp)
            write_run(interim, "tiktok_20261015_195636", [rec("a")], limit=60)
            write_run(interim, "tiktok_20261019_090000", [rec("b")])
            write_run(interim, "tiktok_20261019_100000", [rec("c")], manifest=False)
            chosen, skipped = select_runs(interim)
            self.assertEqual([r.run_id for r in chosen], ["tiktok_20261019_090000"])
            reasons = dict(skipped)
            self.assertIn("run uji", reasons["tiktok_20261015_195636"])
            self.assertIn("manifest", reasons["tiktok_20261019_100000"])

    def test_explicit_runs_override_test_run_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            interim = Path(tmp)
            write_run(interim, "tiktok_20261015_195636", [rec("a")], limit=60)
            chosen, _ = select_runs(interim, only=["tiktok_20261015_195636"])
            self.assertEqual(len(chosen), 1)


@unittest.skipUnless(HAS_PANDAS, "butuh pandas dan pyarrow (pip install -e \".[analysis]\")")
class EndToEndTest(unittest.TestCase):
    def test_writes_versioned_outputs_and_report(self):
        from types import SimpleNamespace

        from src.process import run

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            write_run(data_dir / "interim", "tiktok_20261019_090000", [
                rec("v1", item_type="post", text="Kompilasi #MayorTeddy", hashtags=["mayorteddy"]),
                rec("c1"), rec("c2", text="@budi"),
            ])
            write_run(data_dir / "interim", "x_20261019_100000", [
                rec("1", platform="x", item_type="post", parent_id=None, conversation_id="1", language="in"),
                rec("2", platform="x", item_type="reply", parent_id="1", conversation_id="1", language="in"),
            ])
            args = SimpleNamespace(runs=None, exclude_runs=None, include_test_runs=False,
                                   min_words_language=3, data_dir=data_dir)
            self.assertEqual(run(args, LOGGER, "process_tes"), 0)
            self.assertEqual(run(args, LOGGER, "process_tes"), 0)

            processed = data_dir / "processed"
            names = sorted(p.name for p in processed.iterdir())
            self.assertIn("dataset_v01.parquet", names)
            self.assertIn("dataset_v02.parquet", names)   # versi lama tidak ditimpa

            import pandas as pd
            frame = pd.read_parquet(processed / "dataset_v01.parquet")
            self.assertEqual(len(frame), 5)
            self.assertEqual(int(frame.eligible.sum()), 4)
            meta = json.loads((processed / "dataset_v01.metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["steps"]["x"]["eligible"], 2)
            report = (processed / "dataset_v01.report.md").read_text(encoding="utf-8")
            for heading in ("## 1. Run yang dipakai", "## 2. Alur jumlah data", "## 8. Relasi balasan"):
                self.assertIn(heading, report)


if __name__ == "__main__":
    unittest.main()

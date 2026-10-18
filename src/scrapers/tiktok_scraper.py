"""Scraper TikTok — menjawab RQ1 (praktik fan culture).

Yang perlu terambil: video per hashtag/kata kunci beserta caption, metadata,
dan komentarnya. Konten fan-edit, kompilasi, dan video reaksi adalah sasaran
utamanya, jadi caption dan hashtag ikut disimpan sebagai penanda praktik
produksi konten turunan.

Catatan: seluruh teknik analitik berbasis teks, sehingga isi video tidak
diproses. Yang disimpan adalah caption, hashtag, metadata, dan komentar.
(Lihat keputusan terbuka nomor 5 pada lembar Acuan TK-1.)

Cara akses: library omkarcloud/tiktok-scraper (third_party/), yang memanggil
API web TikTok tanpa login dan tanpa API key. TikTok Research API tidak
tersedia untuk Indonesia (lihat docs/decisions.md).

Sumber video, dibaca dari config/keywords.yaml:
    kata_kunci             -> pencarian video (edisi Indonesia), urutan --tiktok-sort
    hashtag                -> video per hashtag (urutan ranking TikTok)
    akun_target.tiktok     -> video terbaru akun, hanya bila --with-accounts

Hanya video yang dibuat di dalam rentang periode yang disimpan. Komentar pada
video tersebut diambil semua sampai batas --comment-pages, termasuk komentar
yang ditulis setelah periode selesai.

Urutan pencarian (--tiktok-sort): "likes" (bawaan) atau "relevance". Pada uji
18 Okt 2026, "relevance" hampir hanya memberi video bulan terakhir (0 dan 18
dari ~60 video masuk periode), sedangkan "likes" memberi 35 dan 40. "likes"
mengutamakan video populer; bias ini dicatat di C3.

Balasan komentar (--tiktok-replies N, bawaan 0): bila N > 0, untuk tiap
komentar yang reply_count > 0 diambil sampai N halaman balasan (~20 per
halaman), disimpan sebagai item_type "reply" dengan parent_id = ID komentar.
Satu halaman = satu permintaan tambahan per komentar, jadi run jauh lebih lama.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Iterator

from src.common.anonymize import hash_username
from src.scrapers import _vendor
from src.scrapers._common import ScraperRuntime, date_ranges, in_ranges, parse_time
from src.scrapers.base import BaseScraper

# Sebelum mencari, library membuka satu halaman tiktok.com untuk mendapatkan
# cookie sesi. Bawaannya halaman profil /@tiktok, yang dari IP Indonesia
# dijawab dengan halaman anti-bot. /explore tidak diblokir (diuji 15 Okt 2026).
BOOT_PATH = "/explore"
SEARCH_COUNTRY = "id"


def load_library() -> SimpleNamespace:
    _vendor.load("tiktok")
    from tiktok import fetch, refs
    from tiktok.discovery import get_hashtag_posts
    from tiktok.search import search_videos
    from tiktok.users import get_posts
    from tiktok.videos import get_comment_replies, get_comments

    fetch.BOOT_PATH = BOOT_PATH
    return SimpleNamespace(
        search_videos=lambda query, cursor, sort: search_videos(query, country=SEARCH_COUNTRY, sort=sort,
                                                                 cursor=cursor),
        hashtag_videos=lambda tag, cursor: get_hashtag_posts(refs.resolve_hashtag(tag), cursor=cursor),
        user_videos=lambda user, cursor: get_posts(refs.resolve_user(user), cursor=cursor),
        comments=lambda video_id, cursor: get_comments({"id": video_id, "short_link": None}, cursor=cursor),
        replies=lambda video_id, comment_id, cursor: get_comment_replies(
            {"id": video_id, "short_link": None}, comment_id, cursor=cursor),
    )


class TikTokScraper(ScraperRuntime, BaseScraper):
    platform = "tiktok"

    def __init__(self, *args, library: SimpleNamespace | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._library = library

    @property
    def lib(self) -> SimpleNamespace:
        if self._library is None:
            self._library = load_library()
        return self._library

    def collect(self, limit: int | None = None) -> Iterator[dict]:
        self.ranges = date_ranges(self.keywords, self.options.window)
        self._done_videos: set[str] = set()

        def search(query, cursor):
            return self.lib.search_videos(query, cursor, sort=self.options.tiktok_sort)

        sources = [("kata_kunci", kw, search) for kw in self.keywords.get("kata_kunci", [])]
        sources += [("hashtag", tag.lstrip("#"), self.lib.hashtag_videos) for tag in self.keywords.get("hashtag", [])]
        if self.options.with_accounts:
            accounts = self.keywords.get("akun_target", {}).get("tiktok", [])
            sources += [("akun", acc.lstrip("@"), self.lib.user_videos) for acc in accounts]
        self.logger.info("TikTok: %d sumber akan ditelusuri", len(sources))

        for kind, value, fetch_page in sources:
            query = f"{kind}:{value}"
            self.logger.info("TikTok: menelusuri %s", query)
            yield from self._videos(query, value, fetch_page, stop_when_older=(kind == "akun"))

    def _videos(self, query, value, fetch_page, stop_when_older=False) -> Iterator[dict]:
        cursor = None
        earliest = min(start for start, _ in self.ranges)
        for page in range(1, self.options.max_pages + 1):
            try:
                result = fetch_page(value, cursor)
            except Exception as exc:
                self.fail(f"{query} halaman {page}", exc)
                return
            if self.archive:
                self.archive.save(result, label="tiktok_videos")
            videos = result.get("videos") or []
            self.logger.info("TikTok: %s halaman %d, %d video", query, page, len(videos))

            too_old = False
            for video in videos:
                self.stats["videos_seen"] += 1
                if not in_ranges(video.get("created_at"), self.ranges):
                    self.stats["out_of_period"] += 1
                    created = parse_time(video.get("created_at"))
                    if stop_when_older and not video.get("is_pinned") and created and created < earliest:
                        too_old = True
                    continue
                if video["id"] in self._done_videos:
                    continue
                self._done_videos.add(video["id"])
                yield self._video_record(video, query)
                if (video.get("stats") or {}).get("comment_count"):
                    yield from self._comments(video, query)

            cursor = result.get("next_cursor")
            if too_old or not result.get("has_more") or not cursor:
                return
            self.pause()

    def _comments(self, video, query) -> Iterator[dict]:
        cursor = None
        for page in range(1, self.options.comment_pages + 1):
            self.pause()
            try:
                result = self.lib.comments(video["id"], cursor)
            except Exception as exc:
                self.fail(f"komentar video {video['id']} halaman {page}", exc)
                return
            if self.archive:
                self.archive.save(result, label="tiktok_comments")
            for comment in result.get("comments") or []:
                yield self._comment_record(comment, video, query)
                if self.options.tiktok_replies > 0 and (comment.get("reply_count") or 0) > 0:
                    yield from self._replies(comment, video, query)
            cursor = result.get("next_cursor")
            if not result.get("has_more") or not cursor:
                return

    def _replies(self, comment, video, query) -> Iterator[dict]:
        cursor = None
        for page in range(1, self.options.tiktok_replies + 1):
            self.pause()
            try:
                result = self.lib.replies(video["id"], comment["id"], cursor)
            except Exception as exc:
                self.fail(f"balasan komentar {comment['id']} halaman {page}", exc)
                return
            if self.archive:
                self.archive.save(result, label="tiktok_replies")
            for reply in result.get("replies") or []:
                yield self._comment_record(reply, video, query, parent_id=comment["id"])
            cursor = result.get("next_cursor")
            if not result.get("has_more") or not cursor:
                return
        self.stats["reply_page_cap_reached"] += 1

    def _video_record(self, video: dict, query: str) -> dict:
        stats = video.get("stats") or {}
        return self.to_unified(
            item_type="post",
            item_id=str(video["id"]),
            parent_id=None,
            conversation_id=str(video["id"]),
            author_hash=_hash((video.get("author") or {}).get("username")),
            text=video.get("description"),
            created_at=video.get("created_at"),
            like_count=stats.get("like_count"),
            reply_count=stats.get("comment_count"),
            share_count=stats.get("share_count"),
            # tanpa username: link asli TikTok berbentuk /@<username>/video/<id>
            url=f"https://www.tiktok.com/@/video/{video['id']}",
            query=query,
        )

    def _comment_record(self, comment: dict, video: dict, query: str, parent_id: str | None = None) -> dict:
        parent = parent_id or comment.get("parent_comment_id")
        return self.to_unified(
            item_type="reply" if parent else "comment",
            item_id=str(comment["id"]),
            parent_id=str(parent or video["id"]),
            conversation_id=str(video["id"]),
            author_hash=_hash((comment.get("user") or {}).get("username")),
            text=comment.get("text"),
            created_at=comment.get("created_at"),
            like_count=comment.get("like_count"),
            reply_count=comment.get("reply_count"),
            share_count=None,
            url=comment.get("link"),
            query=query,
        )


def _hash(username: str | None) -> str | None:
    return hash_username(username) if username else None

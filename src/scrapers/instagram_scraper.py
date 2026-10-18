"""Scraper Instagram — menjawab RQ2 (distribusi sentimen).

Yang perlu terambil: unggahan tentang Teddy beserta seluruh komentarnya.
Kolom komentar pada satu unggahan yang sama kerap memuat kekaguman dan kritik
berdampingan, dan perbandingan itulah yang diukur pada RQ2, sehingga komentar
pada satu unggahan sebaiknya diambil utuh, bukan sebagian.

Cara akses: library omkarcloud/instagram-scraper (third_party/), tanpa login.
Instagram hanya menampilkan "top reels" kepada pengunjung yang belum login:
sekitar 20-30 unggahan per kata kunci atau hashtag, tanpa tab terbaru dan
tanpa filter tanggal. Keterbatasan ini dicatat di C3.

Sumber unggahan, dibaca dari config/keywords.yaml:
    kata_kunci              -> halaman populer kata kunci (bawaan)
    hashtag                 -> halaman hashtag (bawaan)
    akun_target.instagram   -> linimasa akun, hanya bila --with-accounts.
                               Akun privat dilewati (lihat C6).

Hasil pencarian tidak memuat tanggal dan jumlah like, jadi tiap unggahan
dilengkapi lewat satu permintaan detail sebelum disaring berdasarkan periode.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Iterator

from src.common.anonymize import hash_username
from src.scrapers import _vendor
from src.scrapers._common import ScraperRuntime, date_ranges, in_ranges, parse_time
from src.scrapers.base import BaseScraper


def load_library() -> SimpleNamespace:
    _vendor.load("instagram")
    from instagram import refs
    from instagram.discovery import hashtag_posts, search_keyword
    from instagram.posts import get_comments, get_details
    from instagram.users import get_posts

    return SimpleNamespace(
        keyword_posts=lambda query, cursor: search_keyword(query, cursor=cursor),
        hashtag_posts=lambda tag, cursor: hashtag_posts(refs.resolve_tag(tag), cursor=cursor),
        user_posts=lambda user, cursor: get_posts(refs.resolve_user(user), cursor=cursor),
        details=lambda code: get_details(refs.resolve_post(code)),
        comments=lambda code, cursor: get_comments(refs.resolve_post(code), cursor=cursor),
    )


class InstagramScraper(ScraperRuntime, BaseScraper):
    platform = "instagram"

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
        self._done_posts: set[str] = set()

        sources = [("kata_kunci", kw, self.lib.keyword_posts) for kw in self.keywords.get("kata_kunci", [])]
        sources += [("hashtag", tag.lstrip("#"), self.lib.hashtag_posts) for tag in self.keywords.get("hashtag", [])]
        if self.options.with_accounts:
            accounts = self.keywords.get("akun_target", {}).get("instagram", [])
            if not accounts:
                self.logger.warning("--with-accounts dipakai tapi akun_target.instagram masih kosong (menunggu C1).")
            sources += [("akun", acc.lstrip("@"), self.lib.user_posts) for acc in accounts]
        self.logger.info("Instagram: %d sumber akan ditelusuri", len(sources))

        for kind, value, fetch_page in sources:
            query = f"{kind}:{value}"
            self.logger.info("Instagram: menelusuri %s", query)
            # Halaman populer hanya menjawab huruf kecil: "Mayor Teddy" -> 0
            # unggahan, "mayor teddy" -> 12 (diuji 15 Okt 2026).
            yield from self._posts(query, value.lower(), fetch_page, from_account=(kind == "akun"))

    def _posts(self, query, value, fetch_page, from_account=False) -> Iterator[dict]:
        cursor = None
        earliest = min(start for start, _ in self.ranges)
        for page in range(1, self.options.max_pages + 1):
            try:
                result = fetch_page(value, cursor)
            except Exception as exc:
                self.fail(f"{query} halaman {page}", exc)
                return
            if self.archive:
                self.archive.save(result, label="instagram_posts")
            if from_account and result.get("is_private"):
                self.stats["private_accounts_skipped"] += 1
                self.logger.warning("Instagram: @%s akun privat, dilewati.", value)
                return
            posts = result.get("posts") or []
            self.logger.info("Instagram: %s halaman %d, %d unggahan", query, page, len(posts))

            too_old = False
            for post in posts:
                self.stats["posts_seen"] += 1
                if post.get("code") in self._done_posts:
                    continue
                if not post.get("published_at"):
                    # hasil pencarian belum memuat tanggal dan statistik
                    searched = post
                    post = self._details(post)
                    if post is None:
                        continue
                    _keep_play_count(post, searched)
                if not in_ranges(post.get("published_at"), self.ranges):
                    self.stats["out_of_period"] += 1
                    created = parse_time(post.get("published_at"))
                    if from_account and not post.get("is_pinned") and created and created < earliest:
                        too_old = True
                    continue
                self._done_posts.add(post["code"])
                yield self._post_record(post, query)
                if (post.get("stats") or {}).get("comment_count") != 0:
                    yield from self._comments(post, query)

            cursor = result.get("next_cursor")
            if too_old or not result.get("has_more") or not cursor:
                return
            self.pause()

    def _details(self, post: dict) -> dict | None:
        self.pause()
        try:
            detail = self.lib.details(post["code"])
        except Exception as exc:
            self.fail(f"detail unggahan {post.get('code')}", exc)
            return None
        if self.archive:
            self.archive.save(detail, label="instagram_details")
        return detail

    def _comments(self, post, query) -> Iterator[dict]:
        cursor = None
        for page in range(1, self.options.comment_pages + 1):
            self.pause()
            try:
                result = self.lib.comments(post["code"], cursor)
            except Exception as exc:
                self.fail(f"komentar unggahan {post['code']} halaman {page}", exc)
                return
            if self.archive:
                self.archive.save(result, label="instagram_comments")
            for comment in result.get("comments") or []:
                yield self._comment_record(comment, post, query)
            cursor = result.get("next_cursor")
            if not result.get("has_more") or not cursor:
                return
        self.stats["comment_page_cap_reached"] += 1

    def _post_record(self, post: dict, query: str) -> dict:
        stats = post.get("stats") or {}
        return self.to_unified(
            item_type="post",
            item_id=str(post["id"]),
            parent_id=None,
            conversation_id=str(post["id"]),
            author_hash=_hash((post.get("owner") or {}).get("username")),
            text=post.get("caption"),
            created_at=post.get("published_at"),
            like_count=stats.get("like_count"),
            reply_count=stats.get("comment_count"),
            share_count=None,
            view_count=stats.get("play_count") or stats.get("view_count"),
            url=post.get("link"),
            query=query,
        )

    def _comment_record(self, comment: dict, post: dict, query: str) -> dict:
        parent = comment.get("parent_comment_id")
        return self.to_unified(
            item_type="reply" if parent else "comment",
            item_id=str(comment["id"]),
            parent_id=str(parent or post["id"]),
            conversation_id=str(post["id"]),
            author_hash=_hash((comment.get("user") or {}).get("username")),
            text=comment.get("text"),
            created_at=comment.get("created_at"),
            like_count=comment.get("like_count"),
            reply_count=comment.get("reply_count"),
            share_count=None,
            url=f"https://www.instagram.com/p/{post['code']}/c/{comment['id']}/",
            query=query,
        )


def _keep_play_count(detail: dict, searched: dict) -> None:
    """Hasil pencarian memuat jumlah putar reel, detail kadang tidak."""
    stats = detail.setdefault("stats", {}) or {}
    if stats.get("play_count") is None:
        stats["play_count"] = (searched.get("stats") or {}).get("play_count")
    detail["stats"] = stats


def _hash(username: str | None) -> str | None:
    return hash_username(username) if username else None

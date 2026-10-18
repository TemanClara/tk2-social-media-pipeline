"""Bagian yang dipakai bersama oleh scraper X, TikTok, dan Instagram.

Isinya: opsi run dari command line, rentang tanggal dari keywords.yaml,
penghitung statistik untuk manifest, dan jeda antar permintaan.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from src.common.http import polite_sleep


@dataclass(frozen=True)
class RunOptions:
    max_pages: int = 5          # halaman hasil per kueri/hashtag/akun
    comment_pages: int = 10     # halaman komentar per unggahan
    with_accounts: bool = False # ikut ambil dari akun_target (TikTok/Instagram)
    window: str = "periode"     # "periode" | "peristiwa"


def _parse_day(value) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def date_ranges(keywords: dict, window: str = "periode") -> list[tuple[datetime, datetime]]:
    """Rentang waktu pengumpulan, dalam UTC, dari config/keywords.yaml.

    "periode"   : satu rentang dari periode.mulai sampai akhir hari periode.selesai.
    "peristiwa" : satu rentang per peristiwa_pemicu, mulai tanggal peristiwa
                  sampai `jendela_hari` hari sesudahnya. Ini tafsiran dari
                  "di sekitar peristiwa" dan masih perlu dikonfirmasi ke C1.
    """
    if window == "periode":
        start = _parse_day(keywords["periode"]["mulai"])
        end = _parse_day(keywords["periode"]["selesai"]) + timedelta(days=1)
        return [(_utc(start), _utc(end))]
    if window == "peristiwa":
        ranges = []
        for event in keywords.get("peristiwa_pemicu", []):
            start = _parse_day(event["tanggal"])
            end = start + timedelta(days=int(event.get("jendela_hari", 14)) + 1)
            ranges.append((_utc(start), _utc(end)))
        if not ranges:
            raise ValueError("peristiwa_pemicu kosong di config/keywords.yaml")
        return ranges
    raise ValueError(f"window tidak dikenal: {window}")


def _utc(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc)


def parse_time(value) -> datetime | None:
    """ISO 8601 (dengan 'Z' atau offset) menjadi datetime UTC; None bila kosong."""
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def in_ranges(value, ranges) -> bool:
    moment = parse_time(value)
    return moment is not None and any(start <= moment < end for start, end in ranges)


class ScraperRuntime:
    """Dicampurkan ke scraper: opsi run, statistik, dan jeda.

    run_scrape.py mengisi `options` lalu membaca `stats` untuk manifest,
    sehingga base.py tidak perlu diubah.
    """

    options: RunOptions = RunOptions()

    @property
    def stats(self) -> Counter:
        if not hasattr(self, "_stats"):
            self._stats = Counter()
        return self._stats

    def pause(self) -> None:
        polite_sleep(self.settings.request_delay_seconds)

    def fail(self, what: str, exc: Exception) -> None:
        """Catat kegagalan satu permintaan tanpa menghentikan run."""
        self.stats["errors"] += 1
        self.logger.error("%s gagal: %s: %s", what, type(exc).__name__, exc)

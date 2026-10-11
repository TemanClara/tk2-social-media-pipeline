"""Permintaan HTTP yang sopan: jeda tetap, retry dengan backoff, logging.

Dipakai oleh scraper yang mengambil data lewat HTTP biasa. Scraper yang
memakai library khusus (misalnya Playwright) tetap memanggil polite_sleep()
agar jeda antar permintaan seragam di semua platform (lihat C6 Etika).
"""

from __future__ import annotations

import logging
import random
import time

import requests

logger = logging.getLogger("tk2")

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def polite_sleep(base_seconds: float) -> None:
    """Jeda antar permintaan, diberi variasi acak agar polanya tidak kaku."""
    time.sleep(base_seconds * random.uniform(0.8, 1.3))


def make_session(headers: dict | None = None) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
            ),
            "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
        }
    )
    if headers:
        session.headers.update(headers)
    return session


def get_with_retry(
    session: requests.Session,
    url: str,
    *,
    params: dict | None = None,
    max_retries: int = 4,
    delay_seconds: float = 2.0,
    timeout: int = 30,
) -> requests.Response | None:
    """GET dengan retry eksponensial. Mengembalikan None bila tetap gagal.

    Status 429 (rate limited) dihormati: bila server mengirim Retry-After,
    nilainya dipakai sebagai lama tunggu.
    """
    for attempt in range(1, max_retries + 1):
        try:
            response = session.get(url, params=params, timeout=timeout)
        except requests.RequestException as exc:
            wait = delay_seconds * (2 ** (attempt - 1))
            logger.warning("Gagal menghubungi %s (%s). Coba lagi dalam %.1fs", url, exc, wait)
            time.sleep(wait)
            continue

        if response.status_code == 200:
            polite_sleep(delay_seconds)
            return response

        if response.status_code in RETRYABLE_STATUS:
            retry_after = response.headers.get("Retry-After")
            wait = float(retry_after) if retry_after else delay_seconds * (2 ** (attempt - 1))
            logger.warning(
                "Status %s dari %s. Menunggu %.1fs (percobaan %d/%d)",
                response.status_code, url, wait, attempt, max_retries,
            )
            time.sleep(wait)
            continue

        logger.error("Status %s dari %s. Tidak dicoba ulang.", response.status_code, url)
        return None

    logger.error("Menyerah pada %s setelah %d percobaan.", url, max_retries)
    return None

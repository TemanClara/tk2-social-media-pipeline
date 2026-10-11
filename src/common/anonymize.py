"""Pseudonimisasi username.

Username diganti hash agar identitas pengguna tidak tersimpan dalam dataset,
sementara analisis yang membutuhkan "akun yang sama atau bukan" tetap bisa
dilakukan (lihat C6 Etika).

SALT dibaca dari .env sehingga hash tidak dapat dibalik oleh pihak luar yang
hanya memegang dataset.
"""

from __future__ import annotations

import hashlib
import os


def hash_username(username: str, length: int = 16) -> str:
    salt = os.getenv("PSEUDONYM_SALT", "")
    if not salt:
        raise RuntimeError(
            "PSEUDONYM_SALT belum diisi di .env. "
            "Isi dengan string acak panjang, lalu jangan diubah lagi "
            "selama pengumpulan data agar hash tetap konsisten."
        )
    digest = hashlib.sha256((salt + username.lower().strip()).encode("utf-8"))
    return digest.hexdigest()[:length]

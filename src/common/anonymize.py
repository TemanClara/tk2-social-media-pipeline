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
import re

# @username di dalam teks. Tidak cocok dengan alamat email (huruf sebelum @)
# dan tidak ikut menelan titik di akhir kalimat ("halo @budi.").
MENTION = re.compile(r"(?<![\w@])@([A-Za-z0-9_](?:[A-Za-z0-9_.]*[A-Za-z0-9_])?)")


def mask_mentions(text: str | None) -> str | None:
    """Ganti tiap @username di teks dengan @user_<hash>.

    Hash-nya sama dengan hash_username(), jadi akun yang sama selalu menjadi
    token yang sama, dan di TikTok/Instagram cocok dengan author_hash akun itu.
    """
    if not text:
        return text
    return MENTION.sub(lambda m: f"@user_{hash_username(m.group(1))}", text)


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

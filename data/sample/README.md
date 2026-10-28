# data/sample

Berisi contoh kecil keluaran scraping yang **sudah teranonimisasi**, sebagai
bukti bahwa pipeline berjalan.

Aturan:

- Username wajib sudah berupa hash, bukan nama asli.
- Cukup beberapa puluh baris per platform, bukan dataset penuh.
- Data mentah lengkap disimpan di `data/raw/` dan tidak pernah di-commit.

Isi saat ini:

| Berkas | Asal | Masuk dataset akhir? |
|---|---|---|
| `tiktok_sample.*` | Run A dataset akhir (`tiktok_20261025_144837`) | Ya |
| `x_sample.*`, `instagram_sample.*` | Run uji 15 Okt 2026 dengan `PSEUDONYM_SALT` sementara | Tidak. Disimpan sebagai bukti bahwa scraper X dan Instagram sudah diuji; dataset akhir hanya TikTok (`docs/decisions.md` bagian 6) |

Cuplikan disamarkan lebih jauh dari dataset (`src/make_sample.py`): @mention
diganti `@[pengguna]`, teks dipotong 80 karakter, dan kolom `url` dikosongkan.

# Data

Tiga lapis, masing-masing dengan peran berbeda.

| Folder | Isi | Masuk repo? |
|---|---|---|
| `raw/` | Respons asli dari platform, dikompresi apa adanya, belum diubah sama sekali | Tidak |
| `interim/` | Record yang sudah dipetakan ke skema terpadu, format JSONL, plus `manifest.json` tiap run | Tidak |
| `processed/` | Dataset siap analisis hasil pembersihan dan deduplikasi (bagian C4) | Tidak |
| `sample/` | Contoh kecil teranonimisasi sebagai bukti pipeline berjalan | Ya |

Alasan `raw/` dipisah dari `interim/`: pengambilan ulang data media sosial
mahal dan belum tentu berhasil, karena unggahan bisa dihapus dan akses bisa
diblokir. Dengan menyimpan respons aslinya, kesalahan parsing yang baru
ketahuan belakangan bisa diperbaiki tanpa scraping ulang.

## Kamus data (skema terpadu)

Berlaku sama di ketiga platform. Sumbernya `UNIFIED_FIELDS` di
`src/scrapers/base.py`; ubah di sana, lalu perbarui tabel ini.

| Kolom | Tipe | Isi | Catatan |
|---|---|---|---|
| `platform` | teks | `tiktok`, `instagram`, atau `x` | |
| `item_type` | teks | `post`, `comment`, `reply`, `quote` | |
| `item_id` | teks | ID unik di platform asal | Dipakai untuk deduplikasi |
| `parent_id` | teks | ID unggahan atau komentar induk | Kosong bila unggahan utama |
| `conversation_id` | teks | ID percakapan | Wajib ada di X untuk RQ3 |
| `author_hash` | teks | Username yang sudah dipseudonimkan | Hash SHA-256 bergaram, lihat C6 |
| `text` | teks | Isi unggahan atau komentar | |
| `created_at` | ISO 8601 | Waktu unggah | |
| `like_count` | angka | Jumlah suka | Kosong bila platform tidak menyediakan |
| `reply_count` | angka | Jumlah balasan | |
| `share_count` | angka | Jumlah bagikan | |
| `url` | teks | Tautan ke unggahan asli | |
| `query` | teks | Kata kunci, hashtag, atau akun yang memunculkan record | Untuk menelusuri asal data |
| `_scraped_at` | ISO 8601 | Waktu pengambilan | Ditambahkan otomatis |
| `_run_id` | teks | ID run | Menghubungkan record ke `manifest.json` |

## Manifest tiap run

Tiap run menulis `interim/<run_id>/manifest.json` berisi parameter yang
dipakai, salinan isi `config/keywords.yaml` saat itu, jumlah data yang masuk,
status akhir, serta versi Python dan commit kode. Jalankan `make stats` untuk
merekap seluruh run menjadi satu tabel. Angka di laporan sebaiknya diambil
dari sini, bukan diketik ulang, supaya C1, C4, C5, dan README tidak berbeda.

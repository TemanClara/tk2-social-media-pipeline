# Data

Tiga lapis, masing-masing dengan peran berbeda.

| Folder | Isi | Masuk repo? |
|---|---|---|
| `raw/` | Respons asli dari platform, dikompresi apa adanya, belum diubah sama sekali | Tidak |
| `interim/` | Record yang sudah dipetakan ke skema terpadu, format JSONL, plus `manifest.json` tiap run | Tidak |
| `processed/` | Dataset siap analisis hasil pembersihan dan deduplikasi | Tidak |
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
| `item_type` | teks | `post`, `comment`, `reply`, `quote` | Lihat "Komentar dan balasan" di bawah |
| `item_id` | teks | ID unik di platform asal | Dipakai untuk deduplikasi |
| `parent_id` | teks | ID unggahan atau komentar induk | Kosong bila unggahan utama |
| `conversation_id` | teks | ID unggahan paling atas di percakapan itu | Di X, `quote` punya `conversation_id` sendiri; wajib ada di X untuk RQ3 |
| `author_hash` | teks | Username yang sudah dipseudonimkan | Hash SHA-256 bergaram |
| `text` | teks | Isi unggahan atau komentar | Dengan `--mask-mentions`, tiap @username diganti `@user_<hash>` |
| `created_at` | ISO 8601 | Waktu unggah | |
| `like_count` | angka | Jumlah suka | Kosong bila platform tidak menyediakan |
| `reply_count` | angka | Jumlah tanggapan langsung | Pada `post` TikTok/Instagram: jumlah komentar. Pada `comment`: jumlah balasan. Pada X: jumlah reply |
| `share_count` | angka | Jumlah bagikan | X: `retweet_count`; kosong untuk Instagram dan komentar |
| `view_count` | angka | Jumlah tayang/putar | X: `impression_count` (belum diverifikasi di data nyata); TikTok: jumlah putar video; Instagram: jumlah putar reel. Kosong untuk komentar dan balasan |
| `hashtags` | daftar teks | Hashtag yang muncul di `text`, huruf kecil tanpa `#`, tanpa duplikat | Diambil dari teks dengan pola yang sama di ketiga platform; daftar kosong bila tidak ada |
| `language` | teks | Kode bahasa yang diberikan platform | X: `lang` (kode yang dipakai X belum diverifikasi di data nyata); TikTok: deteksi otomatis TikTok, bisa keliru untuk komentar pendek; Instagram: selalu kosong |
| `url` | teks | Tautan ke unggahan asli | Di `processed/` dikosongkan untuk `comment`/`reply`/`quote`, karena tautannya membuka profil penulis |
| `query` | teks | Kata kunci, hashtag, atau akun yang memunculkan record | Untuk menelusuri asal data |
| `_scraped_at` | ISO 8601 | Waktu pengambilan | Ditambahkan otomatis |
| `_run_id` | teks | ID run | Menghubungkan record ke `manifest.json` |

## Komentar dan balasan

`comment` dan `reply` adalah dua hal berbeda:

- `comment`: tanggapan langsung ke unggahan (TikTok, Instagram).
  `parent_id` = ID unggahan.
- `reply` di TikTok: tanggapan ke sebuah komentar (bagian "Lihat balasan").
  `parent_id` = ID komentar. Hanya diambil bila `--tiktok-replies` > 0.
- `reply` di X: X tidak membedakan komentar, jadi semua tanggapan berupa
  post. Tanggapan ke sebuah post (termasuk ke reply lain) tercatat sebagai
  `reply`, dan `parent_id` = ID post yang ditanggapi.
- `quote` (X saja): post yang mengutip post lain. `parent_id` = ID post yang
  dikutip.

```
TikTok/Instagram                        X
post (video)                            post
 ├─ comment   parent_id = post           ├─ reply  parent_id = post
 │   └─ reply parent_id = comment        │   └─ reply parent_id = reply
 └─ comment   parent_id = post           └─ quote  parent_id = post
```

Di TikTok dan Instagram, semua record dalam satu pohon memiliki
`conversation_id` yang sama (ID unggahan). Di X, `reply` ikut
`conversation_id` post paling atas, tetapi `quote` memulai percakapan baru:
`conversation_id`-nya adalah ID quote itu sendiri, dan hubungannya ke post
yang dikutip hanya lewat `parent_id`. Instagram saat ini hanya mengambil `comment`; balasan di bawah komentar
Instagram tidak diambil.

## Dataset processed (`make process`)

`src/process.py` menggabungkan semua run penuh di `interim/` menjadi satu
dataset analisis. Dataset akhir hanya berisi run TikTok (lihat
`docs/decisions.md` bagian 6); bila ada run X atau Instagram di `interim/`,
keluarkan dengan `--exclude-runs`. Record **tidak dihapus**; setiap kriteria eksklusi
menjadi kolom `flag_*`, dan kolom `eligible` bernilai `true` bila record lolos
semua kriteria. Untuk analisis, filter `eligible == true`.

| Langkah | Aturan |
|---|---|
| Pilih run | Semua run di `interim/`, kecuali run uji (memakai `--limit`) dan run tanpa `manifest.json`. Atur dengan `--runs`, `--exclude-runs`, `--include-test-runs` |
| Buang | Hanya record tanpa `item_id` atau dengan platform tak dikenal |
| Dedup | Kunci `(platform, item_id)`; disimpan versi `_scraped_at` terbaru. Pengaman bila run dari laptop berbeda digabung, karena `_seen_<platform>.txt` hanya berlaku di satu laptop |
| `text_clean` | NFKC, URL → `[URL]`, @mention (termasuk `@user_<hash>`) → `[USER]`, spasi dirapikan. Tanpa huruf kecil, hapus emoji, normalisasi slang, atau stopword; itu diputuskan per teknik di tahap analisis dari kolom `text` asli |
| Simpan | `processed/dataset_vNN.parquet` (analisis), `.csv` (Excel/anotasi), `.metadata.json` (asal-usul), `.report.md` (ringkasan jumlah data). Versi lama tidak ditimpa |

Kolom tambahan:

| Kolom | Jenis | Arti |
|---|---|---|
| `text_clean` | | Teks untuk analisis (lihat di atas) |
| `flag_text_missing` | eksklusi | Teks kosong atau hanya penanda media, mis. `[Foto]` |
| `flag_non_indonesian` | eksklusi | Kode `language` jelas bukan Indonesia **dan** teks minimal 3 kata (lihat catatan bahasa) |
| `flag_mention_only` | eksklusi | Isinya hanya @mention, boleh disertai emoji atau tanda baca |
| `flag_repeated_by_author` | eksklusi | Komentar ganda: teks sama dari `author_hash` yang sama di platform yang sama. Hanya comment/reply/quote; kemunculan paling awal tidak ditandai; teks sama dari akun berbeda tidak ditandai |
| `flag_out_of_period` | eksklusi | `created_at` di luar `periode` (UTC, sama dengan scraper). Scraper hanya menyaring unggahan, jadi komentar yang ditulis setelah periode tertangkap di sini |
| `flag_created_at_invalid` | eksklusi | Waktu tidak terbaca |
| `flag_author_not_hashed` | eksklusi | `author_hash` bukan 16 karakter hex; nilainya dikosongkan |
| `flag_item_type_invalid` | eksklusi | `item_type` di luar `post`/`comment`/`reply`/`quote` |
| `flag_parent_missing` | info | comment/reply/quote tanpa `parent_id` |
| `flag_conversation_missing` | info | Record X tanpa `conversation_id` (RQ3) |
| `flag_negative_count` | info | Angka engagement negatif; nilainya dikosongkan (nol tetap nol) |
| `eligible` | | Tidak terkena flag eksklusi mana pun |

**Catatan bahasa.** Kode bahasa dari platform tidak selalu bisa dipercaya
(TikTok keliru untuk teks pendek, Instagram kosong). Kode `id` dan `in`
dianggap Indonesia; `ms`, `jv`, `su`, `tl`, `und`, `un` (TikTok: bahasa tidak terdeteksi), `zxx`, dan kode khusus X
`qam`/`qct`/`qht`/`qme`/`qst` tidak ditandai karena sering tertukar dengan
bahasa Indonesia informal atau tidak menunjukkan bahasa. Kode lain ditandai
hanya bila teksnya minimal 3 kata (`--min-words-language`). Distribusi kode
lengkap ada di `report.md` bagian 6.

**Belum ditandai otomatis:** spam dan relevansi terhadap figur. Keduanya
dinilai saat anotasi manual.

## Manifest tiap run

Tiap run menulis `interim/<run_id>/manifest.json` berisi parameter yang
dipakai, salinan isi `config/keywords.yaml` saat itu, jumlah data yang masuk,
status akhir, serta versi Python dan commit kode. Jalankan `make stats` untuk
merekap seluruh run menjadi satu tabel.

# Pipeline Pengumpulan Data — Analitika Media Sosial (TK-2)

Pengumpulan data percakapan publik mengenai **Teddy Indra Wijaya** di TikTok,
sebagai tindak lanjut proposal TK-1 "Analisis Hubungan Parasosial dan Fan
Culture terhadap Figur Pemerintahan Non-Elektoral di Media Sosial".

Dataset akhir hanya berasal dari **TikTok** (alasannya
di [`docs/decisions.md`](docs/decisions.md#6-fokus-satu-platform-tiktok)).
Scraper X dan Instagram tetap ada di repo dan sudah diuji, tetapi tidak dipakai
untuk dataset akhir.

## Pertanyaan penelitian dan datanya

| RQ | Pertanyaan ringkas | Data TikTok yang diambil |
|---|---|---|
| RQ1 | Praktik *fan culture* apa yang muncul dan bagaimana persebarannya menurut empat elemen *politicised fandom* | Video per kata kunci dan hashtag beserta caption, hashtag, metadata, dan komentar |
| RQ2 | Bagaimana distribusi sentimen komentar, terbagi antara ekspresi bercorak *fan culture* dan wacana kritis | Komentar pada video yang sama |
| RQ3 | Bagaimana pengguna yang mengekspresikan dukungan merespons komentar kritis dalam utas balasan | Balasan komentar (`item_type = reply`, `parent_id` = ID komentar) |

Cara akses: library open-source omkarcloud tanpa login (tidak resmi), karena
TikTok Research API tidak tersedia untuk Indonesia. Alasan pemilihannya ada di
[`docs/decisions.md`](docs/decisions.md).

## Struktur folder

```
config/keywords.yaml     parameter pengumpulan: kata kunci, hashtag, akun, periode, peristiwa
src/common/              modul bersama: konfigurasi, HTTP, penyimpanan, manifest, hash
src/scrapers/            satu berkas per platform, plus _common.py (opsi run, rentang
                         waktu) dan _vendor.py (pemuat library third_party)
src/run_scrape.py        perintah untuk menjalankan scraping
src/summarize_runs.py    rekap jumlah data seluruh run
src/make_sample.py       cuplikan teranonimisasi untuk data/sample/ dan docs/evidence/
src/process.py           gabung run penuh jadi dataset analisis + laporan (C4)
tests/                   tes unit, tanpa jaringan dan tanpa biaya
third_party/             salinan library omkarcloud untuk TikTok dan Instagram (MIT)
data/raw/                respons asli dari platform — tidak di-commit
data/interim/            record ternormalisasi + manifest tiap run — tidak di-commit
data/processed/          dataset siap analisis (C4) — tidak di-commit
data/sample/             contoh kecil teranonimisasi sebagai bukti
docs/scrapers.md         cara kerja tiap scraper, semua opsi, hasil uji coba
docs/decisions.md        catatan keputusan API vs scraping (bahan tulisan C3)
docs/evidence/           tangkapan layar dan cuplikan bukti scraping
logs/                    log tiap run — tidak di-commit
```

Penjelasan tiga lapis data dan kamus kolomnya ada di [`data/README.md`](data/README.md).

## Instalasi

Butuh Python 3.10 atau lebih baru (diuji dengan Python 3.13).

```bash
git clone https://github.com/TemanClara/tk2-social-media-pipeline.git
cd tk2-social-media-pipeline
make setup
```

`make setup` membuat virtualenv di `.venv`, memasang dependensi dari
`pyproject.toml` beserta tambahan `scrapers` (`curl_cffi` dan `marshmallow`,
dibutuhkan scraper TikTok dan Instagram), dan menyalin `.env.example` menjadi
`.env` bila belum ada. Jalankan `make` tanpa argumen untuk melihat seluruh
perintah yang tersedia.

Tanpa `make`, langkahnya setara dengan:

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[scrapers]"
cp .env.example .env
```

### Mengunci versi

Daftar dependensi ada di `pyproject.toml` dengan versi dipatok pada rentang
minor yang sama. `make lock` menulis versi persis yang sedang terpasang ke
`requirements.lock.txt`; berkas ini **belum dibuat**. Setelah dibuat dan
di-commit, anggota tim yang ingin lingkungan identik memasang dengan
`pip install -r requirements.lock.txt`.

## Konfigurasi

1. Buka `.env` (dibuat oleh `make setup`; tidak ikut ter-*commit*) dan isi:

   | Variabel | Wajib untuk | Isi |
   |---|---|---|
   | `X_BEARER_TOKEN` | X | Bearer Token dari X Developer Console. Terikat ke akun dan saldo pemiliknya, jangan dibagikan |
   | `X_MAX_POSTS_READ` | X | Batas post yang dibaca per run, karena tiap post ditagih. Bawaan 2000 |
   | `PSEUDONYM_SALT` | semua platform | String acak panjang untuk hash username |
   | `REQUEST_DELAY_SECONDS` | semua platform | Jeda antar permintaan. Bawaan 2.0 |
   | `MAX_RETRIES` | X | Jumlah percobaan ulang. Bawaan 4 |

   TikTok dan Instagram diakses tanpa login, jadi tidak butuh kredensial.

   Untuk membuat `PSEUDONYM_SALT`:

   ```bash
   .venv/bin/python -c "import secrets; print(secrets.token_hex(32))"
   ```

   Salt tidak boleh diubah selama pengumpulan data, supaya hash konsisten.
   Bagikan hanya lewat jalur pribadi, kepada anggota tim yang ikut menjalankan
   scraping atau modul yang meng-hash username.

2. Buka `config/keywords.yaml` dan sesuaikan mengikuti hasil penguncian C1:

   | Bagian | Dipakai untuk |
   |---|---|
   | `periode` | Rentang `--window periode` (bawaan) |
   | `peristiwa_pemicu` | Rentang `--window peristiwa`: tanggal tiap peristiwa dan `jendela_hari` |
   | `kata_kunci`, `hashtag` | Sumber pencarian di ketiga platform; di X digabung menjadi satu kueri |
   | `akun_target` | Sumber tambahan TikTok/Instagram, hanya dipakai dengan `--with-accounts` |
   | `bahasa` | Filter `lang:` pada kueri X |
   | `volume_target` | Target jumlah data (belum dipakai kode, untuk rujukan laporan) |

3. Cek kesiapan tanpa mengambil data (ganti `tiktok` dengan `x` atau
   `instagram` untuk scraper lain). Yang diharapkan: baris terakhir
   `Dry-run lolos.`

   ```bash
   .venv/bin/python -m src.run_scrape --platform tiktok --dry-run
   ```

## Menjalankan

```bash
make test             # tes unit, tanpa jaringan dan tanpa biaya
make smoke            # dry-run TikTok: cek konfigurasi tanpa mengambil data
make scrape-x         # jalankan scraping X dengan opsi bawaan
make scrape-tiktok    # jalankan scraping TikTok dengan opsi bawaan
make scrape-instagram # jalankan scraping Instagram dengan opsi bawaan
make stats            # rekap jumlah data seluruh run
make process          # gabung run penuh jadi dataset analisis + laporan
```

Atau langsung, misalnya uji kecil lalu run penuh:

```bash
.venv/bin/python -m src.run_scrape --platform tiktok --limit 20
.venv/bin/python -m src.run_scrape --platform x --window peristiwa
```

Untuk X, uji kecil tetap berbayar; turunkan `X_MAX_POSTS_READ` di `.env` dulu.
Kalau run terputus, jalankan perintah yang sama lagi; item yang sudah
tersimpan dilewati.

Pilihan perintah:

| Argumen | Bawaan | Arti |
|---|---|---|
| `--platform` | (wajib) | `x`, `tiktok`, atau `instagram` |
| `--dry-run` | mati | periksa konfigurasi, kredensial, dan folder tanpa menyentuh jaringan |
| `--limit N` | tanpa batas | berhenti setelah N record tersimpan, berguna saat uji coba |
| `--max-pages N` | 5 | halaman hasil per kata kunci/hashtag/akun (X: per rentang waktu) |
| `--comment-pages N` | 10 | halaman komentar per unggahan (TikTok, Instagram) |
| `--with-accounts` | mati | ikut ambil unggahan dari `akun_target` (TikTok, Instagram) |
| `--window` | `periode` | `periode` (seluruh periode) atau `peristiwa` (jendela per `peristiwa_pemicu`) |
| `--x-sort` | `relevancy` | urutan pencarian X: `relevancy` (paling relevan) atau `recency` (terbaru) |
| `--tiktok-sort` | `likes` | urutan pencarian kata kunci TikTok: `likes` (paling banyak like) atau `relevance` |
| `--tiktok-replies N` | 0 | halaman balasan per komentar TikTok; 0 = balasan tidak diambil |
| `--x-budget` | `rata` | pembagian `X_MAX_POSTS_READ` antar rentang waktu: `rata` (dibagi per rentang) atau `bersama` (dipakai berurutan) |
| `--mask-mentions` | mati | samarkan @username di dalam teks menjadi `@user_<hash>` |
| `--batch-size N` | 500 | jumlah record per berkas keluaran |

Nilai yang dipakai tercatat di `manifest.json` tiap run. Penjelasan cara kerja
tiap scraper, pengaruh tiap opsi, dan hasil uji cobanya ada di
[`docs/scrapers.md`](docs/scrapers.md).

Cuplikan teranonimisasi untuk bukti (`data/sample/` dan `docs/evidence/`):

```bash
.venv/bin/python -m src.make_sample data/interim/<run_id>
```

### Pengumpulan dataset akhir (TikTok)

Dua run, supaya data RQ1–RQ2 pasti lengkap dulu sebelum balasan (RQ3) yang
memakan waktu lama:

| Run | Perintah (opsi) | Untuk | Perkiraan |
|---|---|---|---|
| A | `--max-pages 3 --comment-pages 2 --mask-mentions` | Video dan komentar dari semua kata kunci dan hashtag (RQ1, RQ2) | ±300–550 permintaan, ±20–40 menit |
| B | `--max-pages 1 --comment-pages 1 --tiktok-replies 1 --mask-mentions` | Balasan pada halaman komentar teratas dari video halaman pertama tiap sumber (RQ3) | ±1.000–2.000 permintaan, ±1–2 jam |

Perkiraan kasar dari ±4 detik per permintaan pada run uji 15 Okt
(`docs/evidence/`) dan jumlah video yang masuk periode pada uji 18 Okt;
angka sebenarnya ada di `duration_seconds` manifest.
Video dan komentar yang sudah diambil run A dilewati di run B (dicatat
sebagai `duplicates`), jadi yang baru tertulis hanya balasan. Kedua run
memakai `--window periode` (bawaan) dan `--tiktok-sort likes` (bawaan).

Sebelum run A, hapus `data/raw/_seen_tiktok.txt` dan folder run uji lama di
`data/raw/` serta `data/interim/` bila ada, supaya hash dan dedup dimulai
bersih dengan `PSEUDONYM_SALT` final.

Di Windows (PowerShell), ganti `.venv/bin/python` dengan
`.venv\Scripts\python`, dan jalankan perintah `make` secara langsung, misalnya
`.venv\Scripts\python -m src.process`.

Run boleh dihentikan dengan Ctrl+C. Data yang sudah tertulis tetap tersimpan
dan tetap dipakai `src.process` (status `interrupted` di manifest). Karena
sumber ditelusuri berurutan (kata kunci dulu, lalu hashtag), run yang
dihentikan di tengah membuat sumber terakhir kurang terwakili; catat di C5.

### Dari data mentah ke dataset analisis

Setelah semua run penuh selesai:

```bash
make process
```

Hasilnya di `data/processed/`: `dataset_vNN.parquet` untuk analisis,
`dataset_vNN.csv` untuk dibuka di Excel, `dataset_vNN.metadata.json` berisi
asal-usul data, dan `dataset_vNN.report.md` berisi alur jumlah data, kriteria
eksklusi per platform, sebaran waktu, bahasa, dan kelengkapan kolom. Angka C4
dan C5 diambil dari `report.md`. Run uji (yang memakai `--limit`) otomatis
tidak dipakai. Aturan lengkapnya ada di
[`data/README.md`](data/README.md#dataset-processed-make-process).

## Keluaran

```
data/raw/<run_id>/<label>_00001.json.gz   respons asli per halaman, untuk parsing ulang
data/raw/_seen_<platform>.txt             ID yang sudah diambil, lintas run
data/interim/<run_id>/batch_0001.jsonl    record ternormalisasi, satu per baris
data/interim/<run_id>/manifest.json       parameter, statistik, status run
logs/<run_id>.log                         log lengkap run
```

`<run_id>` berbentuk `<platform>_<YYYYMMDD>_<HHMMSS>` (waktu lokal), misalnya
`tiktok_20261019_090000`. `<label>` menunjukkan jenis respons: `x_search`,
`x_replies`, `x_quotes`, `tiktok_videos`, `tiktok_comments`, `tiktok_replies`,
`instagram_posts`, `instagram_details`, atau `instagram_comments`. Berkas di
`data/raw/` memuat username asli, jadi jangan pernah di-commit atau dibagikan.

### Membaca record

Setiap baris `.jsonl` adalah satu record dengan kolom yang sama di ketiga
platform. Contoh bentuknya (nilai dikarang untuk ilustrasi):

```json
{"platform": "tiktok", "item_type": "comment", "item_id": "7600000000000000002",
 "parent_id": "7600000000000000001", "conversation_id": "7600000000000000001",
 "author_hash": "3f9a1c0b7d2e4a68", "text": "keren banget pak",
 "created_at": "2025-03-01T10:15:00Z", "like_count": 12, "reply_count": 0,
 "share_count": null, "view_count": null, "hashtags": [], "language": "id",
 "url": "https://www.tiktok.com/@/video/7600000000000000001?comment_id=7600000000000000002",
 "query": "kata_kunci:Mayor Teddy",
 "_scraped_at": "2026-10-19T02:00:00+00:00", "_run_id": "tiktok_20261019_090000"}
```

Arti lengkap tiap kolom ada di [`data/README.md`](data/README.md). Yang
paling sering keliru dibaca:

- **`comment` dan `reply` berbeda.** `comment` menanggapi unggahan, `reply` di
  TikTok menanggapi komentar. Di X semua tanggapan adalah `reply`, dan
  `quote` adalah post yang mengutip post lain.
- **`parent_id`** menunjuk ke induk langsung; **`conversation_id`** ke
  unggahan paling atas, sehingga satu percakapan bisa dikelompokkan. Di X,
  `quote` memulai percakapan baru.
- **`reply_count`** pada unggahan TikTok/Instagram berarti jumlah komentar;
  pada komentar berarti jumlah balasan.
- **Kolom kosong** (`null`) berarti platform tidak menyediakan data itu,
  bukan error. Contoh: `share_count` Instagram, `language` Instagram.
- **Waktu dalam UTC.** `created_at`, `_scraped_at`, dan kolom `mulai` pada
  `make stats` memakai UTC, bukan WIB (WIB = UTC + 7 jam).
- **`query`** menunjukkan sumber yang memunculkan record. TikTok/Instagram:
  `kata_kunci:...`, `hashtag:...`, atau `akun:...`. X: kata kunci/hashtag yang
  muncul di teks.

### Manifest dan rekap

Setiap run menulis `manifest.json` berisi parameter yang dipakai, salinan
isi `config/keywords.yaml` saat itu, statistik (`counts`), status akhir
(`completed`, `interrupted`, atau `failed`), serta versi Python dan commit
kode. Arti tiap angka di `counts` ada di
[`docs/scrapers.md`](docs/scrapers.md#perilaku-bersama). Angka jumlah data di
laporan diambil dari `make stats`, bukan diketik ulang, supaya C1, C4, C5, dan
README tidak saling berbeda.

## Catatan etika

- Hanya mengambil konten dari akun publik; akun privat dilewati.
- TikTok dan Instagram diakses tanpa login lewat library tidak resmi. Di
  TikTok, sesi dibuka lewat halaman `/explore` karena halaman bawaannya
  diblokir anti-bot dari IP Indonesia. Kedua hal ini dinilai di C6.
- Username disimpan dalam bentuk hash bergaram, tidak dalam bentuk asli.
  Kolom `url` tidak memuat username. @username di dalam teks bisa disamarkan
  dengan `--mask-mentions`.
- Jeda antar permintaan diatur lewat `REQUEST_DELAY_SECONDS` dan diberi
  variasi acak. Status 429 dari X dihormati dengan menunggu sesuai
  `Retry-After` atau `x-rate-limit-reset`.
- Data mentah tidak pernah masuk ke repositori publik. Cuplikan di
  `data/sample/` disamarkan lebih jauh (mention diganti, teks dipotong, tautan
  dikosongkan).

Uraian lengkapnya ada di bagian C6 laporan.

## Tim

| Nama | Bagian |
|---|---|
| Azzahra Salsabila | C1 Kebutuhan Data, C7 Penutup |
| Clara Aurelia Setiady | C2 Pipeline, C6 Etika |
| Kania Almyra Bilqist | C3 Metode Pengumpulan Data, repositori dan scraper |
| Nafia Levana Aulia | C4 Implementasi Pipeline, C5 Kualitas Data |

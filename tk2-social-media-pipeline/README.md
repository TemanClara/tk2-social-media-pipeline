# Pipeline Pengumpulan Data — Analitika Media Sosial (TK-2)

Pengumpulan data percakapan publik mengenai **Teddy Indra Wijaya** di TikTok,
Instagram, dan X, sebagai tindak lanjut proposal TK-1 "Analisis Hubungan
Parasosial dan Fan Culture terhadap Figur Pemerintahan Non-Elektoral di Media
Sosial".

## Pertanyaan penelitian dan platformnya

| RQ | Pertanyaan ringkas | Platform utama | Data yang diambil |
|---|---|---|---|
| RQ1 | Praktik *fan culture* apa yang muncul dan bagaimana persebarannya | TikTok | Video per hashtag beserta caption, metadata, dan komentar |
| RQ2 | Bagaimana distribusi sentimen antara ekspresi penggemar dan wacana kritis | Instagram | Komentar pada unggahan akun berita dan akun apresiasi |
| RQ3 | Bagaimana penggemar merespons kritik | X | Post, balasan, *quote-tweet*, dan ID percakapan |

## Struktur folder

```
config/keywords.yaml     parameter pengumpulan: kata kunci, hashtag, akun, periode
src/common/              modul bersama: konfigurasi, HTTP, penyimpanan, manifest, hash
src/scrapers/            satu berkas per platform
src/run_scrape.py        perintah untuk menjalankan scraping
src/summarize_runs.py    rekap jumlah data seluruh run
data/raw/                respons asli dari platform — tidak di-commit
data/interim/            record ternormalisasi + manifest tiap run — tidak di-commit
data/processed/          dataset siap analisis (C4) — tidak di-commit
data/sample/             contoh kecil teranonimisasi sebagai bukti
docs/decisions.md        catatan keputusan API vs scraping (bahan tulisan C3)
docs/evidence/           tangkapan layar dan cuplikan bukti scraping
```

Penjelasan tiga lapis data dan kamus kolomnya ada di [`data/README.md`](data/README.md).

## Instalasi

Butuh Python 3.10 atau lebih baru.

```bash
git clone <URL-REPO-INI>
cd tk2-social-media-pipeline
make setup
```

`make setup` membuat virtualenv di `.venv`, memasang dependensi dari
`pyproject.toml`, dan menyalin `.env.example` menjadi `.env` bila belum ada.
Jalankan `make` tanpa argumen untuk melihat seluruh perintah yang tersedia.

Tanpa `make`, langkahnya setara dengan:

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
cp .env.example .env
```

### Mengunci versi

Daftar dependensi ada di `pyproject.toml` dengan versi dipatok pada rentang
minor yang sama. Setelah pemasangan berhasil, jalankan `make lock` untuk
menulis versi persis yang terpasang ke `requirements.lock.txt`, lalu commit
berkas itu. Anggota tim yang ingin lingkungan identik memasang dengan
`pip install -r requirements.lock.txt`.

## Konfigurasi

1. Salin berkas contoh kredensial:

   ```bash
   cp .env.example .env
   ```

2. Buka `.env`, isi kredensial tiap platform dan `PSEUDONYM_SALT` dengan
   string acak yang panjang. Nilai salt harus sama antar anggota tim dan
   tidak boleh diubah selama pengumpulan data, supaya hash username
   konsisten. Berkas `.env` tidak ikut ter-*commit*.

3. Buka `config/keywords.yaml`, sesuaikan kata kunci, hashtag, daftar akun,
   dan periode mengikuti hasil penguncian C1.

## Menjalankan

```bash
make smoke            # cek konfigurasi tanpa mengambil data
make scrape-x         # jalankan scraping X
make stats            # rekap jumlah data seluruh run
```

Atau langsung:

```bash
python -m src.run_scrape --platform x --limit 50
```

Pilihan perintah:

| Argumen | Arti |
|---|---|
| `--platform` | `x`, `tiktok`, atau `instagram` |
| `--limit` | batas jumlah record, berguna saat uji coba |
| `--batch-size` | jumlah record per berkas keluaran (bawaan 500) |
| `--dry-run` | periksa konfigurasi dan folder tanpa menyentuh jaringan |

## Keluaran

```
data/raw/<run_id>/page_00001.json.gz     respons asli, untuk parsing ulang
data/raw/_seen_<platform>.txt            ID yang sudah diambil, lintas run
data/interim/<run_id>/batch_0001.jsonl   record ternormalisasi
data/interim/<run_id>/manifest.json      parameter, jumlah data, status run
logs/<run_id>.log
```

Setiap baris pada berkas `.jsonl` adalah satu record dengan kolom yang sama
di ketiga platform:

| Kolom | Isi |
|---|---|
| `platform` | `tiktok`, `instagram`, atau `x` |
| `item_type` | `post`, `comment`, `reply`, atau `quote` |
| `item_id` | ID unik di platform asal |
| `parent_id` | ID unggahan atau komentar induk |
| `conversation_id` | ID percakapan, dipakai untuk menelusuri alur balasan pada RQ3 |
| `author_hash` | username yang sudah dipseudonimkan |
| `text` | isi teks |
| `created_at` | waktu unggah (ISO 8601) |
| `like_count`, `reply_count`, `share_count` | metrik interaksi |
| `url` | tautan ke unggahan asli |
| `query` | kata kunci, hashtag, atau akun yang memunculkan record ini |

Berkas `_seen_<platform>.txt` menyimpan ID yang sudah pernah diambil, sehingga
run yang terputus dapat dilanjutkan tanpa mengulang dari awal.

Setiap run juga menulis `manifest.json` berisi parameter yang dipakai, salinan
isi `config/keywords.yaml` saat itu, jumlah data yang masuk, dan status akhir.
Angka jumlah data di laporan diambil dari `make stats`, bukan diketik ulang,
supaya C1, C4, C5, dan README tidak saling berbeda.

## Catatan etika

- Hanya mengambil konten dari akun publik.
- Username disimpan dalam bentuk hash, tidak dalam bentuk asli.
- Jeda antar permintaan diatur lewat `REQUEST_DELAY_SECONDS`; status 429
  dihormati dengan menunggu sesuai `Retry-After`.
- Data mentah tidak pernah masuk ke repositori publik.

Uraian lengkapnya ada di bagian C6 laporan.

## Tim

| Nama | Bagian |
|---|---|
| Azzahra Salsabila | C1 Kebutuhan Data, C7 Penutup |
| Clara Aurelia Setiady | C2 Pipeline, C6 Etika |
| Kania Almyra Bilqist | C3 Metode Pengumpulan Data |
| Nafia Levana Aulia | C4 Implementasi Pipeline, C5 Kualitas Data |

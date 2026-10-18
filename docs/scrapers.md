# Cara Kerja Scraper dan Cara Menjalankannya

Dokumen ini menjelaskan apa yang sebenarnya diambil oleh tiap scraper, dalam
urutan apa, batasnya di mana, dan perintah untuk menjalankannya. Isinya
berdasarkan kode di `src/scrapers/` dan uji coba 15 dan 18 Okt 2026 (bukti di
`docs/evidence/`). Hal yang belum diuji ditandai **belum diuji**.

## Ringkasan

| | X | TikTok | Instagram |
|---|---|---|---|
| Cara akses | X API v2 resmi, bayar per post yang dibaca | Library omkarcloud/tiktok-scraper, tanpa login | Library omkarcloud/instagram-scraper, tanpa login |
| Kredensial di `.env` | `X_BEARER_TOKEN`, `PSEUDONYM_SALT` | `PSEUDONYM_SALT` | `PSEUDONYM_SALT` |
| Sumber bawaan | Satu kueri gabungan `kata_kunci` + `hashtag` | `kata_kunci` dan `hashtag` | `kata_kunci` dan `hashtag` |
| Sumber opsional | (tidak ada) | `akun_target.tiktok` dengan `--with-accounts` | `akun_target.instagram` dengan `--with-accounts` |
| Urutan hasil | `--x-sort`: `relevancy` (bawaan) atau `recency` | Kata kunci: `--tiktok-sort` `likes` (bawaan) atau `relevance`; hashtag: ranking TikTok | "Top reels" pilihan Instagram |
| Filter tanggal | Di sisi API (`start_time`, `end_time`) | Disaring setelah diambil | Disaring setelah diambil |
| Yang ikut diambil | Balasan dan quote-tweet | Komentar, dan balasan komentar bila `--tiktok-replies` > 0 | Komentar |
| `item_type` yang muncul | `post`, `reply`, `quote` | `post`, `comment`, `reply` | `post`, `comment` |

Semua scraper menulis record dengan kolom yang sama (`UNIFIED_FIELDS` di
`src/scrapers/base.py`, kamusnya di `data/README.md`). Username tidak pernah
disimpan; yang disimpan `author_hash`, yaitu SHA-256 dari username (atau ID
akun untuk X) yang diberi `PSEUDONYM_SALT`.

## Rentang waktu: `--window`

Berlaku untuk ketiga platform, dibaca dari `config/keywords.yaml`.

| Nilai | Artinya |
|---|---|
| `periode` (bawaan) | Satu rentang dari `periode.mulai` sampai akhir hari `periode.selesai` (sekarang 1 Okt 2024 s/d 30 Sep 2026) |
| `peristiwa` | Satu rentang per `peristiwa_pemicu`: dari tanggal peristiwa sampai `jendela_hari` hari sesudahnya |

Dengan isi `keywords.yaml` sekarang, `peristiwa` menghasilkan tiga rentang:
20 Okt–3 Nov 2024, 25 Feb–11 Mar 2025, dan 13–27 Mei 2026.

Tafsiran "sampai 14 hari sesudahnya" masih perlu dikonfirmasi ke C1, karena
komentar di `keywords.yaml` menulis "di sekitar peristiwa". Kalau yang
dimaksud sebelum dan sesudah, cukup ubah `date_ranges()` di
`src/scrapers/_common.py`.

Untuk X, rentang dikirim ke API, jadi pencariannya memang di tanggal itu.
Untuk TikTok dan Instagram, pencariannya tidak bisa diberi tanggal; rentang
hanya dipakai untuk **membuang** hasil yang di luar rentang. Akibatnya
`peristiwa` lebih berguna untuk X daripada untuk dua platform lainnya.

## X

**Alur per rentang waktu:**

1. **Pencarian arsip penuh** (`GET /2/tweets/search/all`) dengan satu kueri
   gabungan, misalnya:
   ```
   ("Teddy Indra Wijaya" OR "Mayor Teddy" OR "Letkol Teddy" OR "Seskab Teddy" OR #mayorteddy) -is:retweet lang:id
   ```
   Kuerinya dibentuk otomatis dari `kata_kunci`, `hashtag`, dan `bahasa` di
   `keywords.yaml`. Retweet dibuang karena teksnya terpotong dan metriknya
   milik post asli. Urutannya diatur `--x-sort`:
   - `relevancy` (bawaan): post paling relevan menurut X. Di uji 18 Okt, 20
     post tersebar dari Nov 2024 sampai Jun 2026.
   - `recency`: terbaru lebih dulu. Di uji 15 Okt, semua post bertanggal
     30 Sep 2026, hari terakhir periode.
2. **Balasan**, hanya untuk post yang `reply_count > 0`: pencarian
   `conversation_id:<id> -is:retweet` mulai dari waktu post itu dibuat. Satu
   percakapan hanya diambil sekali per run. Pencarian balasan memakai urutan
   bawaan X dan tidak mengikuti `--x-sort`.
3. **Quote-tweet**, hanya untuk post yang `quote_count > 0`
   (`GET /2/tweets/:id/quote_tweets`).

Hasil pencarian di langkah 1 bisa berupa balasan atau quote juga, kalau
teksnya cocok dengan kueri. Jenisnya ditentukan dari `referenced_tweets`.

**Pengaman biaya.** Setiap post yang dibaca ditagih, termasuk yang nanti
dibuang sebagai duplikat.

| Batas | Nilai | Diatur di |
|---|---|---|
| Total post dibaca per run | 2.000 | `X_MAX_POSTS_READ` di `.env` |
| Pembagian jatah antar rentang waktu | `rata` | `--x-budget` |
| Halaman pencarian per rentang | 5 (100 post per halaman) | `--max-pages` |
| Balasan per percakapan | 100 | `MAX_REPLIES` di `x_scraper.py` |
| Quote per post | 50 | `MAX_QUOTES` di `x_scraper.py` |
| Ukuran halaman saat uji | mengikuti `--limit` (min. 10, maks. 100) | `--limit` |

**Pembagian jatah (`--x-budget`).** Rentang waktu diproses berurutan.
Dengan `rata` (bawaan), sisa jatah dibagi rata ke rentang yang belum
diproses: dengan 2.000 post dan tiga peristiwa, peristiwa pertama mendapat
666, dan bila hanya terpakai 100, dua peristiwa berikutnya berbagi 1.900.
Dengan `bersama`, satu jatah dipakai berurutan, sehingga peristiwa pertama
yang ramai bisa menghabiskannya. Untuk `--window periode` (satu rentang)
kedua pilihan sama saja. Pemakaian tiap rentang tercatat sebagai
`posts_read_<tanggal awal>` di manifest.

Begitu jatah sebuah rentang habis, scraper berhenti meminta data untuk
rentang itu dan mencatat `budget_exhausted` di manifest. Parameter `expansions` sengaja tidak dipakai
supaya objek pengguna tidak ikut ditagih.

Dengan `--x-sort recency`, run `--window periode` dan batas 2.000 post
kemungkinan besar hanya mencakup minggu-minggu terakhir periode. Bawaan
`relevancy` menyebar hasil di sepanjang periode, tapi mengutamakan post yang
dianggap X paling relevan, biasanya yang interaksinya tinggi. Bias ini perlu
dicatat di C3.

**Pemetaan kolom:**

| Kolom | Isi |
|---|---|
| `author_hash` | Hash dari `author_id` (ID numerik akun, tetap walau akun ganti username) |
| `text` | `note_tweet.text` bila ada (post panjang, sudah diuji), selain itu `text` |
| `parent_id` | ID post yang dibalas atau dikutip; kosong untuk post biasa |
| `conversation_id` | Dari X. Untuk `reply`: ID post paling atas di utasnya. Untuk `quote`: ID quote itu sendiri, karena quote memulai percakapan baru (hubungannya ke post yang dikutip lewat `parent_id`) |
| `share_count` | `retweet_count` |
| `view_count` | `impression_count` (belum diverifikasi di data nyata) |
| `language` | `lang` dari X (kode yang dipakai belum diverifikasi di data nyata) |
| `query` | Kata kunci/hashtag yang muncul di teks, mis. `Mayor Teddy; #mayorteddy`. Balasan dan quote mewarisi `query` post induknya |
| `url` | `https://x.com/i/status/<id>` (tanpa username) |

**Rate limit.** Status 429 dan 5xx dicoba ulang sampai `MAX_RETRIES` kali
(bawaan 4, di `.env`). Lama tunggunya mengikuti header `Retry-After` atau
`x-rate-limit-reset` dari X, paling lama 15 menit; bila header tidak ada,
tunggu bertambah dua kali lipat tiap percobaan.

## TikTok

**Alur per sumber:**

| Sumber | Cara ambil | Isi per halaman |
|---|---|---|
| `kata_kunci:<kata>` | Pencarian video edisi Indonesia (`country=id`), urutan `--tiktok-sort` | ~20 video |
| `hashtag:<tag>` | Video di bawah hashtag, urutan ranking TikTok | ~30 video |
| `akun:<username>` | Video terbaru akun (hanya dengan `--with-accounts`) | ~35 video |

Untuk tiap video:

1. Video di luar rentang waktu dibuang dan dihitung sebagai `out_of_period`.
   Pada sumber akun, scraper berhenti membuka halaman berikutnya begitu
   menemukan video (yang bukan video sematan) lebih tua dari awal rentang.
2. Video yang sudah diambil dari sumber lain di run yang sama dilewati.
3. Video disimpan sebagai `post`, lalu komentarnya diambil (~50 per halaman,
   sampai `--comment-pages`), kecuali jumlah komentarnya 0.

4. Bila `--tiktok-replies N` lebih dari 0, untuk tiap komentar yang
   `reply_count > 0` diambil sampai N halaman balasan (~20 per halaman).
   Balasan disimpan sebagai `reply` dengan `parent_id` berisi ID komentar.
   Bawaannya 0 (balasan tidak diambil). Bila batas halaman tercapai sebelum
   balasan habis, manifest mencatat `reply_page_cap_reached`.

Balasan bisa mendominasi volume. Di uji 18 Okt dengan `--tiktok-replies 1`,
55 dari 60 record adalah balasan, karena satu komentar populer bisa punya
puluhan balasan. Satu halaman balasan juga berarti satu permintaan tambahan
per komentar, jadi run jauh lebih lama.

**Urutan pencarian (`--tiktok-sort`).** Hanya berlaku untuk sumber kata
kunci; video per hashtag selalu mengikuti ranking TikTok.

| Urutan | "Teddy Indra Wijaya" | "Mayor Teddy" |
|---|---|---|
| `relevance` | 0 dari 58 video masuk periode | 18 dari 58 |
| `likes` (bawaan) | 35 dari 60 | 40 dari 59 |

(Uji 18 Okt 2026, 3 halaman per kata kunci.) Dengan `relevance`, hampir semua
video berasal dari bulan terakhir, setelah periode selesai. `likes`
mengutamakan video populer, jadi video dari akun kecil bisa kurang terwakili;
bias ini perlu dicatat di C3.

**Catatan teknis.** Sebelum mencari, library membuka satu halaman tiktok.com
untuk mendapatkan cookie sesi. Bawaannya halaman `/@tiktok`, yang dari IP
Indonesia dijawab dengan halaman anti-bot. Scraper menggantinya dengan
`/explore` (`BOOT_PATH` di `tiktok_scraper.py`), yang tidak diblokir.

**Pemetaan kolom:**

| Kolom | Video | Komentar |
|---|---|---|
| `parent_id` | kosong | ID video (balasan: ID komentar induk) |
| `conversation_id` | ID video | ID video |
| `reply_count` | jumlah komentar | jumlah balasan |
| `share_count` | jumlah share | kosong |
| `view_count` | jumlah putar video | kosong |
| `language` | deteksi bahasa TikTok untuk caption | deteksi bahasa TikTok untuk komentar (bisa keliru untuk teks pendek; di uji 18 Okt muncul `tr` dan `tl` di antara 38 `id`) |
| `url` | `https://www.tiktok.com/@/video/<id>` | tautan komentar |
| `query` | mis. `kata_kunci:Mayor Teddy` | sama dengan videonya |

Tautan asli TikTok memuat username (`/@<username>/video/<id>`), jadi kolom
`url` sengaja memakai bentuk `/@/video/<id>` yang tetap bisa dibuka.

## Instagram

Semua diambil **tanpa login**, jadi hanya yang ditampilkan Instagram kepada
pengunjung yang belum login.

**Alur per sumber:**

| Sumber | Cara ambil | Isi per halaman |
|---|---|---|
| `kata_kunci:<kata>` | Halaman populer kata kunci (`/popular/<kata>/`) | 12 reels |
| `hashtag:<tag>` | Halaman hashtag | 12 reels |
| `akun:<username>` | Linimasa akun, terbaru lebih dulu (hanya dengan `--with-accounts`) | 12 unggahan |

Untuk tiap unggahan:

1. Hasil kata kunci dan hashtag tidak memuat tanggal dan jumlah like, jadi
   scraper meminta detail unggahan dulu (satu permintaan tambahan per
   unggahan).
2. Unggahan di luar rentang waktu dibuang (`out_of_period`). Pada sumber akun,
   berhenti begitu menemukan unggahan non-sematan yang lebih tua dari awal
   rentang. Akun privat dilewati (`private_accounts_skipped`).
3. Unggahan disimpan sebagai `post`, lalu komentarnya diambil sampai habis
   atau sampai `--comment-pages`. Library meminta 24 komentar per halaman,
   tapi praktiknya hanya ~12–14 yang datang, dan pada sebagian unggahan
   halamannya berhenti lebih awal. Bila batas halaman tercapai sebelum
   komentar habis, manifest mencatat `comment_page_cap_reached`.

**Batasan dari Instagram, bukan dari kode:**

- Kata kunci dan hashtag hanya memberi sekitar 20–30 unggahan teratas, tanpa
  tab terbaru. Volume data Instagram terutama datang dari komentar.
- Halaman populer hanya menjawab huruf kecil ("Mayor Teddy" memberi 0
  unggahan, "mayor teddy" memberi 12). Scraper otomatis mengubah kata kunci
  ke huruf kecil; kolom `query` tetap memakai tulisan di `keywords.yaml`.
- `#mayorteddy` memberi 0 unggahan saat diuji, sedangkan `#teddyindrawijaya`
  memberi 20. Penyebabnya belum diketahui.
- Kolom `reply_count` pada komentar umumnya kosong.

**Pemetaan kolom:** sama seperti TikTok, dengan beberapa perbedaan.
`view_count` berisi jumlah putar reel (diambil dari hasil pencarian bila
detail unggahan tidak memuatnya), `language` selalu kosong karena Instagram
tidak menyediakan kode bahasa, dan `share_count` juga selalu kosong. `url`
komentar berbentuk `https://www.instagram.com/p/<kode>/c/<id komentar>/`.

## Perilaku bersama

**Jeda antar permintaan.** Setiap permintaan ke TikTok dan Instagram diberi
jeda `REQUEST_DELAY_SECONDS` (bawaan 2 detik, di `.env`) dikali angka acak
0,8–1,3, supaya polanya tidak kaku. X memakai jeda yang sama sesudah setiap
permintaan yang berhasil.

**Hashtag.** Kolom `hashtags` diisi dari teks (`text`) dengan pola yang
sama di ketiga platform: huruf kecil, tanpa `#`, tanpa duplikat, urutan
kemunculan. Contoh: caption `Keren #MayorTeddy #fyp` menjadi
`["mayorteddy", "fyp"]`.

**Menyamarkan @username di teks (`--mask-mentions`).** Bawaannya mati. Bila
dinyalakan, tiap @username di `text` diganti `@user_<hash>`, dengan hash yang
sama seperti `author_hash` (SHA-256 bergaram). Akibatnya akun yang sama
selalu menjadi token yang sama, dan di TikTok/Instagram token itu cocok
dengan `author_hash` akun tersebut. Di X tidak cocok, karena `author_hash` X
dibuat dari ID akun, bukan username. Alamat email tidak ikut disamarkan.
Kolom `hashtags` diambil sebelum penyamaran, jadi tidak terpengaruh.

**Kegagalan.** Library TikTok dan Instagram sudah mencoba ulang sendiri
3 kali dengan jeda yang makin panjang (2 detik dikali nomor percobaan). Kalau
masih gagal, scraper kita **tidak berhenti**: halaman atau unggahan itu
dilewati, error dicatat di log dan di `errors` pada manifest, lalu lanjut ke
sumber berikutnya. Run baru berhenti dengan status `failed` kalau ada error
tak terduga, misalnya bug atau konfigurasi salah.

**Melanjutkan run yang terputus.** ID yang sudah tersimpan dicatat di
`data/raw/_seen_<platform>.txt`. Kalau run berhenti (Ctrl+C, internet putus,
laptop mati), jalankan perintah yang sama lagi; item yang sudah ada dilewati
dan dihitung sebagai `duplicates`. Permintaan ke platform tetap dilakukan
ulang, jadi untuk X, post yang dibaca ulang **tetap ditagih**.

**Keluaran tiap run:**

| Lokasi | Isi |
|---|---|
| `data/raw/<run_id>/` | Respons asli tiap halaman, dikompresi (`.json.gz`). Memuat username asli, jangan pernah di-commit |
| `data/interim/<run_id>/batch_*.jsonl` | Record skema terpadu, satu per baris |
| `data/interim/<run_id>/manifest.json` | Parameter run, salinan `keywords.yaml`, statistik, versi kode |
| `logs/<run_id>.log` | Log lengkap run |

**Arti angka di `counts` pada manifest:**

| Kunci | Arti |
|---|---|
| `written` | Record yang tersimpan |
| `written_post`, `written_comment`, `written_reply`, `written_quote` | Rincian `written` per `item_type` |
| `duplicates` | Dilewati karena sudah pernah diambil |
| `errors` | Permintaan yang gagal setelah dicoba ulang |
| `out_of_period` | Video/unggahan yang dibuang karena di luar rentang waktu |
| `videos_seen`, `posts_seen` | Video/unggahan yang dilihat sebelum disaring (TikTok, Instagram) |
| `posts_read` | Post yang dibaca dari API, yaitu yang ditagih (X) |
| `budget_exhausted` | Jatah baca sebuah rentang habis (X) |
| `posts_read_<tanggal>` | Post yang dibaca di rentang yang dimulai tanggal itu (X) |
| `comment_page_cap_reached` | Unggahan yang komentarnya terpotong oleh `--comment-pages` (Instagram) |
| `reply_page_cap_reached` | Komentar yang balasannya terpotong oleh `--tiktok-replies` (TikTok) |
| `private_accounts_skipped` | Akun privat yang dilewati (Instagram) |
| `raw_pages` | Jumlah respons mentah yang disimpan |

## Perintah

Semua perintah dijalankan dari folder repo (`cd ~/tk2-social-media-pipeline`).

**Persiapan (sekali saja):**

```bash
make setup
```

Lalu isi `.env`: `X_BEARER_TOKEN`, `PSEUDONYM_SALT`, dan bila perlu
`X_MAX_POSTS_READ`.

**Cek kesiapan tanpa mengambil data:**

```bash
.venv/bin/python -m src.run_scrape --platform x --dry-run
```

Ganti `x` dengan `tiktok` atau `instagram`. Perintah ini memeriksa
kredensial (tanpa menampilkan isinya), library yang dibutuhkan, dan rentang
waktu yang akan dipakai. Yang diharapkan: baris terakhir `Dry-run lolos.`

**Tes unit (tanpa jaringan, tanpa biaya):**

```bash
make test
```

**Uji kecil:**

```bash
.venv/bin/python -m src.run_scrape --platform tiktok --limit 20
```

`--limit` menghentikan run setelah sekian record tersimpan. Untuk X, uji kecil
tetap berbayar; pasang batas baca rendah dulu, misalnya `X_MAX_POSTS_READ=60`
di `.env`.

**Run penuh** (angka hanya contoh, sesuaikan dengan target C1):

```bash
.venv/bin/python -m src.run_scrape --platform x --window peristiwa
```

```bash
.venv/bin/python -m src.run_scrape --platform tiktok --max-pages 10 --comment-pages 5
```

```bash
.venv/bin/python -m src.run_scrape --platform instagram --comment-pages 20
```

**Semua opsi `run_scrape`:**

| Opsi | Bawaan | Fungsi |
|---|---|---|
| `--platform` | (wajib) | `x`, `tiktok`, atau `instagram` |
| `--dry-run` | mati | Cek kesiapan saja |
| `--limit N` | tanpa batas | Berhenti setelah N record tersimpan |
| `--max-pages N` | 5 | Halaman hasil per kueri/hashtag/akun (X: per rentang waktu) |
| `--comment-pages N` | 10 | Halaman komentar per unggahan (TikTok, Instagram) |
| `--with-accounts` | mati | Ikut ambil dari `akun_target` (TikTok, Instagram) |
| `--window` | `periode` | `periode` atau `peristiwa` |
| `--x-sort` | `relevancy` | Urutan pencarian X: `relevancy` atau `recency` |
| `--tiktok-sort` | `likes` | Urutan pencarian kata kunci TikTok: `likes` atau `relevance` |
| `--tiktok-replies N` | 0 | Halaman balasan per komentar TikTok; 0 = tidak diambil |
| `--x-budget` | `rata` | Pembagian `X_MAX_POSTS_READ` antar rentang: `rata` atau `bersama` |
| `--mask-mentions` | mati | Samarkan @username di dalam teks menjadi `@user_<hash>` |
| `--batch-size N` | 500 | Jumlah record per berkas `batch_*.jsonl` |

Semua nilai opsi tercatat di `manifest.json` bagian `params`.

**Rekap semua run** (bahan angka C1, C4, C5):

```bash
make stats
```

**Cuplikan teranonimisasi untuk bukti** (`data/sample/` dan `docs/evidence/`):

```bash
.venv/bin/python -m src.make_sample data/interim/<run_id>
```

Cuplikan menyamarkan @mention di teks, memotong teks menjadi 80 karakter, dan
mengosongkan `url`. Opsi `--rows` (bawaan 30) dan `--max-chars` (bawaan 80)
bisa diubah.

## Belum diuji

- `--window peristiwa` ke API X sungguhan (baru diuji dengan tes unit).
- `--x-budget rata` ke API X sungguhan (baru diuji dengan tes unit).
- Kolom `view_count` (`impression_count`) dan `language` (`lang`) untuk X:
  belum ada run X sejak kolom ini ditambahkan, jadi isi dan kode bahasanya
  belum dilihat di data nyata.
- `--mask-mentions` pada data nyata: uji 18 Okt (80 record TikTok dan
  Instagram) kebetulan tidak memuat @username; perilakunya diuji dengan tes unit.
- `--x-sort relevancy` lewat scraper secara utuh. Yang sudah diuji baru satu
  permintaan pencarian langsung (20 post); pengiriman parameternya oleh
  scraper diuji dengan tes unit.
- `--with-accounts` untuk TikTok dan Instagram dengan akun sungguhan, karena
  `akun_target` masih kosong.
- Run panjang (ratusan permintaan beruntun). Batas sebelum diblokir TikTok
  atau Instagram belum diketahui.

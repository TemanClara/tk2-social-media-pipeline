# Keputusan Pengumpulan Data

Catatan ini menjadi bahan tulisan C3 (Metode Pengumpulan Data). Isi tabel
berikut dari hasil percobaan, bukan dari dugaan — penilaian C3 menuntut
penjelasan endpoint/selector, parameter, kueri, pagination, dan penanganan
error yang nyata.

Uji coba dilakukan 15 dan 18 Okt 2026 dari IP Indonesia. Bukti run ada di
`docs/evidence/`, penjelasan perilaku tiap scraper di `docs/scrapers.md`.
Baris bertanda *(riset awal)* berasal dari pengecekan sebelum 15 Okt dan
tidak diuji ulang.

## 1. API resmi vs scraping, per platform

| Platform | Opsi yang dicoba | Bisa diakses? | Biaya | Data yang didapat | Keputusan | Alasan |
|---|---|---|---|---|---|---|
| X | X API v2 resmi, bayar per pemakaian | Ya | ±$0,005 per post dibaca *(riset awal: kredit turun $0,05 untuk 9 post)* | Post, balasan (`conversation_id`), quote-tweet, metrik, teks panjang (`note_tweet`) | **Dipakai** | Satu-satunya opsi resmi yang memberi struktur balasan untuk RQ3 |
| X | `twscrape` (butuh cookie akun) | Tidak dicoba | Gratis | — | Cadangan | Ketentuan layanan X tidak menganjurkan; API resmi sudah berjalan |
| TikTok | TikTok Research API | Tidak *(riset awal: tidak tersedia untuk Indonesia)* | — | — | Tidak dipakai | Tidak tersedia |
| TikTok | `TikTokApi` 7.3 + Playwright + cookie `ms_token` | Sebagian *(riset awal)* | Gratis | `hashtag.info()` berhasil; `hashtag.videos()` gagal `EmptyResponseException` | Tidak dipakai | Daftar video diblokir deteksi bot; tidak ada pencarian kata kunci video |
| TikTok | `drawrowfly/tiktok-scraper` 1.4.36 (npm, rilis terakhir Mei 2022) | Tidak | Gratis | Profil dan metadata video gagal; user/hashtag/trend kosong | Tidak dipakai | Tidak terawat, tidak lagi cocok dengan TikTok |
| TikTok | `Q-Bukold/TikTok-Content-Scraper` | Sebagian | Gratis | Metadata + berkas video/slide dari daftar ID berhasil; profil diblokir | Tidak dipakai | Tidak ada pencarian kata kunci atau hashtag |
| TikTok | `omkarcloud/tiktok-scraper` (commit `3993cb2`, MIT), tanpa login | Ya, dengan penyesuaian `BOOT_PATH` | Gratis | Pencarian kata kunci, video per hashtag, video akun, komentar, balasan komentar | **Dipakai** | Satu-satunya opsi yang diuji yang memberi pencarian kata kunci dan hashtag beserta komentar |
| Instagram | Meta Content Library (resmi) | Tidak diajukan *(riset awal: review 2–6 minggu)* | — | — | Jalur ideal, tidak ditempuh | Waktu review melewati tenggat |
| Instagram | `Instaloader` dengan akun riset | Tidak dicoba | Gratis | — | Tidak dipakai | Butuh login; opsi tanpa login sudah berjalan |
| Instagram | `omkarcloud/instagram-scraper` (commit `9763ba6`, MIT), tanpa login | Ya | Gratis | Top reels per kata kunci dan hashtag, detail unggahan, komentar, linimasa akun | **Dipakai** | Tanpa akun riset, sehingga tidak ada risiko checkpoint akun |

Kedua library omkarcloud tidak resmi dan disalin ke `third_party/` (lihat
`third_party/README.md`). Implikasi etika dan ketentuan layanannya dibahas di
bagian 4 dan C6.

## 2. Cara akses yang dipakai

| Platform | Endpoint atau selector | Parameter kueri | Cara pagination | Batas yang ditemui |
|---|---|---|---|---|
| X | `GET /2/tweets/search/all` | `query` = `("Teddy Indra Wijaya" OR "Mayor Teddy" OR "Letkol Teddy" OR "Seskab Teddy" OR #mayorteddy) -is:retweet lang:id`; `start_time`, `end_time` per rentang; `sort_order` (`relevancy`/`recency`); `max_results` ≤ 100; `tweet.fields` = `author_id,created_at,conversation_id,public_metrics,referenced_tweets,lang,note_tweet`; tanpa `expansions` | `meta.next_token` → `next_token` | Dengan `recency`, hasil menumpuk di akhir rentang (semua post 30 Sep 2026 pada uji 15 Okt); dengan `relevancy`, tersebar Nov 2024–Jun 2026 (uji 18 Okt) |
| X (balasan) | `GET /2/tweets/search/all` | `query` = `conversation_id:<id> -is:retweet`; `start_time` = waktu post | `next_token`; maks. 100 balasan per percakapan | Hanya untuk post dengan `reply_count > 0` |
| X (quote) | `GET /2/tweets/:id/quote_tweets` | `max_results`, `tweet.fields` sama | `meta.next_token` → `pagination_token`; maks. 50 per post | Hanya untuk post dengan `quote_count > 0` |
| TikTok (kata kunci) | `/api/search/item/full/` (lewat library; permintaan ditandatangani oleh `signer.py` library) | `keyword`, `count=20`, `region=ID`; urutan `likes` mengirim `is_filter_search=1`, `sort_type=1` | `offset` + `search_id` dari halaman pertama | Butuh cookie sesi: library membuka satu halaman dulu. Halaman bawaan `/@tiktok` diblokir dari IP Indonesia, diganti `/explore`. Urutan `relevance` hampir hanya memberi video bulan terakhir |
| TikTok (hashtag) | `/api/challenge/detail/` lalu `/api/challenge/item_list/` | `challengeID`, `count=30` | `cursor` | Urutan mengikuti ranking TikTok, tidak bisa diatur |
| TikTok (akun) | `/api/user/detail/` lalu `/api/post/item_list/` | `secUid`, `count=35` | `cursor` | Belum diuji dengan akun topik (`akun_target` kosong) |
| TikTok (komentar) | `/api/comment/list/` | `aweme_id`, `count=50` | `cursor` | Hanya komentar tingkat atas |
| TikTok (balasan) | `/api/comment/list/reply/` | `item_id`, `comment_id`, `count=20` | `cursor` | Satu permintaan per komentar; balasan bisa mendominasi volume |
| Instagram (kata kunci, hashtag) | GraphQL `PolarisLoggedOutPopularSearchPageQuery` (halaman `/popular/<kata>/`) | kata kunci dalam **huruf kecil** | `cursor`, 12 per halaman | Hanya ±20–30 top reels per kueri, tanpa tab terbaru; huruf kapital memberi 0 hasil; `#mayorteddy` 0 hasil, `#teddyindrawijaya` 20 |
| Instagram (detail) | GraphQL `PolarisLoggedOutDesktopWWWPostRootContentQuery` | kode unggahan | — | Diperlukan karena hasil pencarian tidak memuat tanggal dan like |
| Instagram (komentar) | GraphQL `PolarisLoggedOutDesktopWWWPostCommentsPaginationQuery` | `media_id`, `first=24` | `after` = cursor | Praktiknya ±12–14 komentar per halaman; sebagian unggahan berhenti lebih awal; `reply_count` umumnya kosong |
| Instagram (akun) | Linimasa akun lewat library | username | `cursor`, 12 per halaman | Akun privat dilewati; belum diuji dengan akun topik |

Penyaringan tanggal: X menyaring di sisi API. TikTok dan Instagram tidak
menyediakan filter tanggal, sehingga video/unggahan di luar rentang dibuang
setelah diambil dan dihitung sebagai `out_of_period` di manifest.

## 3. Penanganan error

- Jeda antar permintaan: 2,0 detik × angka acak 0,8–1,3 (lihat
  `REQUEST_DELAY_SECONDS` di `.env`).
- Status yang dicoba ulang (X, `src/common/http.py`): 429, 500, 502, 503, 504.
  Lama tunggu mengikuti `Retry-After` atau `x-rate-limit-reset` (maks.
  15 menit); bila tidak ada, dua kali lipat tiap percobaan.
- Jumlah percobaan maksimum: X 4 kali (`MAX_RETRIES` di `.env`); library
  TikTok dan Instagram 3 kali dengan jeda 2 detik × nomor percobaan, memakai
  sesi baru bila diblokir.
- Bila tetap gagal: halaman atau unggahan itu dilewati, error dicatat di log
  dan di `counts.errors` manifest, run lanjut ke sumber berikutnya. Run
  berstatus `failed` hanya untuk error tak terduga.
- Pengaman biaya X: `X_MAX_POSTS_READ` (bawaan 2.000 post per run). Dengan
  `--x-budget rata` (bawaan), jatah dibagi rata ke tiap rentang waktu dan sisa
  yang tak terpakai ikut ke rentang berikutnya, sehingga dengan
  `--window peristiwa` tiap peristiwa pasti kebagian. Pemakaian per rentang
  tercatat sebagai `posts_read_<tanggal>` di manifest.
- Cara melanjutkan run yang terputus: berkas `_seen_<platform>.txt` di
  `data/raw/`. ID yang sudah tersimpan dilewati saat ditulis, tetapi halaman
  tetap diminta ulang (untuk X tetap ditagih).

## 4. Ketentuan layanan dan robots.txt

Diisi bersama Clara (C6). Catat tanggal pemeriksaan dan poin yang relevan.

| Platform | Tanggal cek | Poin ToS yang relevan | robots.txt |
|---|---|---|---|
| X | | | |
| TikTok | | | |
| Instagram | | | |

Hal yang perlu dinilai di sini: library TikTok dan Instagram bersifat tidak
resmi, dan penggantian `BOOT_PATH` ke `/explore` di TikTok bisa dianggap
mengakali halaman anti-bot.

## 5. Hal yang masih terbuka

- [x] ~~Sumber data RQ2 berubah dari desain TK-1~~ — gugur: RQ2 kini memakai komentar TikTok (bagian 6)
- [x] Pengumpulan penuh dua tahun atau sampel per jendela peristiwa — **penuh** (`--window periode`). Untuk TikTok, `peristiwa` hanya membuang hasil di luar jendela setelah diambil, tidak mengubah apa yang dicari (lihat `docs/scrapers.md`), sehingga tidak menghemat permintaan
- [ ] Tafsiran `jendela_hari`: sesudah tanggal peristiwa (implementasi sekarang) atau di sekitarnya. Tidak berpengaruh selama memakai `periode`
- [x] Target volume — ±1.000 komentar TikTok berbahasa Indonesia yang `eligible`, 300 dianotasi manual (C1). Unit hitung: komentar. `volume_target` di config hanya catatan; volume diatur lewat `--max-pages` dan `--comment-pages`
- [x] Perlakuan konten non-Indonesia — ditandai `flag_non_indonesian` di `src/process.py`, tidak dihapus (lihat `data/README.md`)
- [ ] Bias urutan: `--tiktok-sort likes` dan ranking hashtag TikTok mengutamakan konten populer; perlu dicatat di C3/C5
- [x] Penyamaran @username di dalam teks — **dipakai** (`--mask-mentions`) di run dataset akhir, untuk minimalisasi data (C6). Perlu dikonfirmasi Clara
- [ ] `akun_target.tiktok` masih kosong (C1 baru menyebut nama media, belum handle TikTok); run dataset akhir tanpa `--with-accounts`, jadi konten dari akun fanbase hanya terjaring bila muncul di pencarian kata kunci atau hashtag

## 6. Fokus satu platform: TikTok

Diputuskan 25 Okt 2026. Dataset akhir hanya diambil dari TikTok.

| Pertimbangan | TikTok | Instagram | X |
|---|---|---|---|
| Konten fan (video edit, kompilasi) untuk RQ1 | Ada: caption dan hashtag video | Ada, tetapi hanya ±20–30 top reels per kueri | Sedikit |
| Komentar untuk RQ2 | Ada, ±50 per halaman | ±12–14 per halaman | Ada (balasan) |
| Struktur tanggapan untuk RQ3 | Balasan komentar (`--tiktok-replies`) | Balasan tidak diambil | Balasan dan quote-tweet |
| Kode bahasa | Deteksi otomatis TikTok | Tidak ada | Ada |
| Biaya | Gratis | Gratis | ±$0,005 per post dibaca |

Alasan: dua dari tiga RQ sudah bertumpu pada komentar dan konten fan TikTok,
dan TikTok menyediakan balasan komentar sehingga RQ3 tetap bisa dijawab di
platform yang sama. Fokus pada satu platform juga membuat konteks percakapan
seragam untuk anotasi dan analisis.

Akibatnya:
- RQ3 dirumuskan ulang dari "balasan dan quote-tweet di X" menjadi "utas
  balasan komentar TikTok". "Kelompok penggemar" diganti "pengguna yang
  mengekspresikan dukungan", karena di TikTok tidak ada keanggotaan kelompok
  yang bisa diamati.
- Komentar kritis baru dapat dikenali setelah anotasi manual, sehingga utas
  balasan untuk RQ3 dipilih dari dataset setelah anotasi.
- Temuan hanya berlaku untuk TikTok; bias algoritma rekomendasi dan
  demografi pengguna TikTok membatasi generalisasi (C5).
- Kode bahasa hanya dari deteksi otomatis TikTok, yang keliru untuk teks
  pendek (C5).
- Scraper X dan Instagram tetap di repo beserta bukti ujinya, tetapi run-nya
  tidak masuk dataset akhir.

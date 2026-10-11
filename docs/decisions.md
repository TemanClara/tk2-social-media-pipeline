# Keputusan Pengumpulan Data

Catatan ini menjadi bahan tulisan C3 (Metode Pengumpulan Data). Isi tabel
berikut dari hasil percobaan, bukan dari dugaan — penilaian C3 menuntut
penjelasan endpoint/selector, parameter, kueri, pagination, dan penanganan
error yang nyata.

## 1. API resmi vs scraping, per platform

| Platform | Opsi yang dicoba | Bisa diakses? | Biaya | Data yang didapat | Keputusan | Alasan |
|---|---|---|---|---|---|---|
| X | API resmi / library / scraping HTML | | | | | |
| TikTok | | | | | | |
| Instagram | | | | | | |

## 2. Cara akses yang dipakai

| Platform | Endpoint atau selector | Parameter kueri | Cara pagination | Batas yang ditemui |
|---|---|---|---|---|
| X | | | | |
| TikTok | | | | |
| Instagram | | | | |

## 3. Penanganan error

- Jeda antar permintaan: … detik (lihat `REQUEST_DELAY_SECONDS` di `.env`)
- Status yang dicoba ulang: 429, 500, 502, 503, 504
- Jumlah percobaan maksimum: …
- Cara melanjutkan run yang terputus: berkas `_seen_<platform>.txt` di `data/raw/`

## 4. Ketentuan layanan dan robots.txt

Diisi bersama Clara (C6). Catat tanggal pemeriksaan dan poin yang relevan.

| Platform | Tanggal cek | Poin ToS yang relevan | robots.txt |
|---|---|---|---|
| X | | | |
| TikTok | | | |
| Instagram | | | |

## 5. Hal yang masih terbuka

- [ ] Pengumpulan penuh dua tahun atau sampel per jendela peristiwa (keputusan CP1)
- [ ] Target volume per platform (dari C1)
- [ ] Perlakuan konten non-Indonesia

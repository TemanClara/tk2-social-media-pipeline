# docs/evidence

Bukti bahwa scraping benar-benar dijalankan: manifest dan log tiap run, serta
laporan tahap processing.

## Dataset akhir (TikTok, 25 Okt 2026)

Empat run berikut digabung oleh `src/process.py` menjadi `dataset_v05`
(commit `3963e84`). Parameter persis setiap run, salinan `keywords.yaml` yang
dipakai, dan statistiknya ada di manifest masing-masing.

| Berkas | Run | Status | Record ditulis | Catatan |
|---|---|---|---|---|
| `tiktok_20261025_144837_manifest.json` | A: video + komentar (`--max-pages 3 --comment-pages 2`) | completed | 10.440 (146 video, 10.294 komentar) | 0 error, ±12 menit |
| `tiktok_20261025_150459_manifest.json` | B: balasan (`--max-pages 1 --comment-pages 1 --tiktok-replies 1`) | completed | 5.387 (5.352 balasan, 35 komentar) | 51 permintaan gagal karena gangguan jaringan; sumber 4–8 tidak terambil |
| `tiktok_20261025_155253_manifest.json` | B, lanjutan pertama (perintah sama) | interrupted | 2.460 (2.262 balasan, 194 komentar, 4 video) | Dihentikan manual (Ctrl+C); data yang tertulis tetap dipakai |
| `tiktok_20261025_190404_manifest.json` | B, lanjutan kedua (perintah sama) | completed | 3.363 (3.181 balasan, 179 komentar, 3 video) | 0 error; kata kunci "Teddy Indra Wijaya" dinonaktifkan sementara agar sumber yang sudah diambil dilewati (lihat `keywords_snapshot` di manifest) |
| `dataset_v05.report.md` | Laporan tahap processing | | 21.650 record, 18.783 eligible | Alur jumlah data, flag eksklusi, sebaran waktu, bahasa, kelengkapan kolom, relasi balasan, konsentrasi per video |
| `dataset_v05.metadata.json` | Metadata dataset | | | Run yang dipakai, parameter processing, versi Python/pandas/pyarrow, commit |

Semua `--mask-mentions`, `--window periode`, `--tiktok-sort likes`. Video dan
komentar yang sudah tersimpan dilewati otomatis di run berikutnya
(`_seen_tiktok.txt`), dan `src/process.py` mencatat 0 duplikat antar-run.

## Run uji (15 Okt 2026, tidak masuk dataset akhir)

| Platform | Berkas | Isi |
|---|---|---|
| TikTok | `tiktok_20261015_log.txt` | Log run uji `--limit 60 --max-pages 3 --comment-pages 1` |
| TikTok | `tiktok_20261015_manifest.json` | Parameter, salinan `keywords.yaml`, dan statistik run yang sama |
| Instagram | `instagram_20261015_log.txt` | Log run uji `--limit 40 --max-pages 2 --comment-pages 1` |
| Instagram | `instagram_20261015_manifest.json` | Parameter, salinan `keywords.yaml`, dan statistik run yang sama |
| X | `x_20261015_log.txt` | Log run uji `--limit 20` dengan `X_MAX_POSTS_READ=60` (terbaca 30 post) |
| X | `x_20261015_manifest.json` | Parameter, salinan `keywords.yaml`, dan statistik run yang sama |

Cuplikan keluarannya ada di `data/sample/<platform>_sample.json` dan `.csv`
(30 baris per platform). Cuplikan TikTok sudah dibuat ulang dari run A
dataset akhir; cuplikan X dan Instagram masih dari run uji 15 Okt. Dibuat
dengan:

```
python -m src.make_sample data/interim/<run_id>
```

Catatan untuk run 15 Okt 2026:

- Run uji memakai `PSEUDONYM_SALT` sementara, bukan salt dataset akhir.
  Hash di cuplikan ini tidak akan sama dengan hash di dataset final.
- Cuplikan disamarkan lebih jauh dari dataset: @mention di teks diganti
  `@[pengguna]`, teks dipotong 80 karakter, kolom `url` dikosongkan.
- Cuplikan X dan Instagram 15 Okt dibuat sebelum kolom `view_count`,
  `hashtags`, dan `language` ditambahkan (18 Okt), jadi kolom itu kosong di
  sana. Cuplikan TikTok sudah memuatnya.
- Run 15 Okt dijalankan **sebelum** ada opsi `--x-sort` dan `--tiktok-sort`
  (ditambahkan 18 Okt). Saat itu X memakai urutan terbaru (setara
  `--x-sort recency`) dan TikTok urutan relevan (setara
  `--tiktok-sort relevance`). Bawaan sekarang berbeda: `relevancy` dan `likes`.
- TikTok: 65 dari 67 video yang ditemukan berada di luar periode
  (kebanyakan diunggah setelah 30 Sep 2026), sehingga hanya 2 video yang
  masuk. Lihat `out_of_period` di manifest. Uji ulang 18 Okt dengan urutan
  `likes` memberi 35 dan 40 video masuk periode dari ~60 per kata kunci
  (lihat `docs/scrapers.md`).
- X: field `note_tweet` diterima (teks post panjang utuh). Dengan urutan
  terbaru, semua post di run uji bertanggal 30 Sep 2026 (hari terakhir
  periode). Uji 18 Okt dengan `sort_order=relevancy` memberi 20 post yang
  tersebar dari Nov 2024 sampai Jun 2026.

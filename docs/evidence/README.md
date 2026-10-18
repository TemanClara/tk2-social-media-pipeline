# docs/evidence

Bukti bahwa scraping benar-benar dijalankan: tangkapan layar proses berjalan,
cuplikan log, dan contoh keluaran per platform.

Penamaan: `<platform>_<tanggal>_<keterangan>.png`

## Isi saat ini

| Platform | Berkas | Isi |
|---|---|---|
| TikTok | `tiktok_20261015_log.txt` | Log run uji `--limit 60 --max-pages 3 --comment-pages 1` |
| TikTok | `tiktok_20261015_manifest.json` | Parameter, salinan `keywords.yaml`, dan statistik run yang sama |
| Instagram | `instagram_20261015_log.txt` | Log run uji `--limit 40 --max-pages 2 --comment-pages 1` |
| Instagram | `instagram_20261015_manifest.json` | Parameter, salinan `keywords.yaml`, dan statistik run yang sama |
| X | `x_20261015_log.txt` | Log run uji `--limit 20` dengan `X_MAX_POSTS_READ=60` (terbaca 30 post) |
| X | `x_20261015_manifest.json` | Parameter, salinan `keywords.yaml`, dan statistik run yang sama |

Cuplikan keluarannya ada di `data/sample/<platform>_sample.json` dan `.csv`
(30 baris per platform), dibuat dengan:

```
python -m src.make_sample data/interim/<run_id>
```

Catatan untuk run 15 Okt 2026:

- Run uji memakai `PSEUDONYM_SALT` sementara karena salt tim belum diisi.
  Hash di cuplikan ini tidak akan sama dengan hash di dataset final.
- Cuplikan disamarkan lebih jauh dari dataset: @mention di teks diganti
  `@[pengguna]`, teks dipotong 80 karakter, kolom `url` dikosongkan. Aturan
  ini perlu dikonfirmasi bersama C6.
- TikTok: 65 dari 67 video yang ditemukan berada di luar periode
  (kebanyakan diunggah setelah 30 Sep 2026), sehingga hanya 2 video yang
  masuk. Lihat `out_of_period` di manifest.
- X: field `note_tweet` diterima (teks post panjang utuh). Pencarian arsip
  penuh mengembalikan post terbaru lebih dulu, sehingga semua post di run uji
  bertanggal 30 Sep 2026 (hari terakhir periode). Dengan batas baca 2.000 post,
  run penuh hanya akan mencakup minggu-minggu terakhir periode kecuali memakai
  `--window peristiwa`.

## Tangkapan layar yang perlu diambil

Ambil dengan `Cmd + Shift + 4` lalu seret area yang mau diambil (macOS), dan
simpan ke folder ini dengan nama sesuai format di atas. Jangan ambil layar
yang memperlihatkan isi `.env`, data mentah di `data/raw/`, atau username asli.

| Nama berkas | Yang ditampilkan |
|---|---|
| `semua_<tanggal>_tes.png` | Terminal setelah `make test`, sampai baris `OK` |
| `tiktok_<tanggal>_run.png` | Terminal saat `python -m src.run_scrape --platform tiktok --limit 20` berjalan, sampai baris `Statistik` |
| `instagram_<tanggal>_run.png` | Sama, untuk `--platform instagram` |
| `x_<tanggal>_run.png` | Sama, untuk `--platform x` |
| `<platform>_<tanggal>_sample.png` | `data/sample/<platform>_sample.json` terbuka di VS Code |

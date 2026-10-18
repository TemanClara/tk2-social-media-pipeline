# Library pihak ketiga

Salinan kode dari repositori lain, dipakai oleh scraper TikTok dan Instagram.
Disalin (bukan git submodule) supaya `git clone` biasa sudah cukup untuk
menjalankan pipeline ini.

| Folder | Sumber | Commit | Lisensi |
|---|---|---|---|
| `omkarcloud-tiktok-scraper/` | https://github.com/omkarcloud/tiktok-scraper | `3993cb224bafedcf5defe21a0badeccdd01fad03` | MIT (lihat `LICENSE` di foldernya) |
| `omkarcloud-instagram-scraper/` | https://github.com/omkarcloud/instagram-scraper | `9763ba690a24ba7a91467f22be287730019cfa46` | MIT (lihat `LICENSE` di foldernya) |

Yang dibuang dari salinan: folder `.git`, berkas Docker, dan gambar README.
Selain itu isinya sama persis dengan commit di atas. **Jangan mengedit berkas
di sini.** Penyesuaian dilakukan dari kode kita sendiri (lihat
`src/scrapers/tiktok_scraper.py` untuk penggantian `BOOT_PATH`).

Kedua library punya modul tingkat atas dengan nama yang sama (`config`,
`scraper_errors`, `schema_fields`), jadi `src/scrapers/_vendor.py` hanya
memuat satu library per proses. Satu run memang hanya untuk satu platform.

## Memperbarui

1. Clone repositori sumber dan `git checkout <commit baru>`.
2. Ganti isi folder di sini dengan salinan baru (tanpa `.git`, Docker, dan gambar).
3. Perbarui kolom commit pada tabel di atas.
4. Jalankan `python -m unittest discover tests` lalu uji kecil
   `python -m src.run_scrape --platform tiktok --limit 20`.

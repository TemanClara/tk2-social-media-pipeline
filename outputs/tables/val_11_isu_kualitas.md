| Isu | Temuan | Penanganan |
|---|---|---|
| Data hilang | 389 record tanpa teks; kolom lain kosong hanya menurut desain (mis. jumlah tayang/bagikan pada komentar) | Ditandai flag_text_missing dan dikeluarkan; kosong dibedakan dari nol |
| Duplikasi | 0 ID ganda; 117 komentar ganda dari akun yang sama | Deduplikasi (platform, item_id); komentar ganda ditandai, kemunculan pertama dipertahankan |
| Spam dan noise | 387 record hanya mention; 1 teks panjang berulang dari akun berbeda (3 record); teks berulang lain umumnya pendek dan generik | Mention saja dikeluarkan; relevansi dan spam dinilai saat anotasi |
| Konsistensi relasi | 0 pelanggaran relasi induk–anak dan urutan waktu; 158 balasan eligible berinduk komentar tidak eligible | Konteks utas RQ3 dibaca dari dataset lengkap |
| Temporal | 1.822 record ditulis sesudah periode (hingga 2026-10-25); tidak ada yang sebelum periode | Ditandai flag_out_of_period dan dikeluarkan |
| Bahasa dan teks pendek | 83,8% komentar+balasan eligible berkode id; 240 record asing dikeluarkan; 22,1% berisi ≤2 kata dan 4,8% tanpa huruf | Kode ms/un tidak dikeluarkan; prapemrosesan diputuskan per teknik; aturan emoji di codebook |
| Cakupan dan bias sampling | Terambil 4,8% komentar dan 19,2% balasan dari jumlah yang dilaporkan platform; pencarian diurutkan menurut suka | Dinyatakan sebagai batasan; klaim dibatasi pada percakapan yang paling terlihat |
| Privasi | Username dipseudonimkan; URL komentar dikosongkan; 6 kemunculan pola @ yang kemungkinan mention lolos penyamaran | Data hanya di Drive privat; tanpa kutipan verbatim; regex penyamaran diperbaiki bila dataset dibuat ulang |

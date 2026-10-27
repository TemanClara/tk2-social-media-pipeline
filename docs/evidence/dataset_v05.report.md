# Laporan dataset_v05

Dibuat 2026-10-27T02:49:36.363812+00:00 oleh `src/process.py` (commit 3963e84). Periode 2024-10-01 s/d 2026-09-30 (UTC). Semua waktu di laporan ini dalam UTC.

## 1. Run yang dipakai

| run_id | platform | status | mask_mentions | written (manifest) | dibaca |
|---|---|---|---|---|---|
| tiktok_20261025_144837 | tiktok | completed | True | 10440 | 10440 |
| tiktok_20261025_150459 | tiktok | completed | True | 5387 | 5387 |
| tiktok_20261025_155253 | tiktok | interrupted | True | 2460 | 2460 |
| tiktok_20261025_190404 | tiktok | completed | True | 3363 | 3363 |

**Peringatan:**

- tiktok_20261025_155253: status run `interrupted`.

## 2. Alur jumlah data

`eligible` = lolos semua kriteria eksklusi. Target dari `volume_target` di `keywords.yaml`.

| platform | masuk | dibuang (tanpa ID) | duplikat | dataset | eligible | target |
|---|---|---|---|---|---|---|
| tiktok | 21650 | 0 | 0 | 21650 | 18783 | 1000 |
| **total** | 21650 | 0 | 0 | 21650 | 18783 |  |

## 3. Kriteria eksklusi dan flag

Satu record bisa terkena lebih dari satu flag, jadi kolom tidak dijumlahkan.

| flag | arti | jenis | tiktok |
|---|---|---|---|
| `flag_text_missing` | Teks kosong | eksklusi | 389 |
| `flag_non_indonesian` | Bukan bahasa Indonesia (C1) | eksklusi | 240 |
| `flag_mention_only` | Hanya menandai pengguna lain (C1) | eksklusi | 387 |
| `flag_repeated_by_author` | Komentar ganda dari akun yang sama (C1) | eksklusi | 117 |
| `flag_out_of_period` | Di luar periode (C1) | eksklusi | 1822 |
| `flag_created_at_invalid` | Waktu tidak terbaca | eksklusi | 0 |
| `flag_author_not_hashed` | author_hash bukan hash (privasi) | eksklusi | 0 |
| `flag_item_type_invalid` | item_type tidak dikenal | eksklusi | 0 |
| `flag_parent_missing` | comment/reply/quote tanpa parent_id | info | 0 |
| `flag_conversation_missing` | Record X tanpa conversation_id (RQ3) | info | 0 |
| `flag_negative_count` | Angka engagement negatif (dikosongkan) | info | 0 |

## 4. Jenis item

Angka: dataset (eligible).

| item_type | tiktok |
|---|---|
| post | 153 (147) |
| comment | 10702 (9350) |
| reply | 10795 (9286) |
| quote |  |

## 5. Sebaran waktu record eligible (per bulan, UTC)

| bulan | tiktok |
|---|---|
| 2024-10 | 204 |
| 2024-11 | 51 |
| 2024-12 | 24 |
| 2025-01 | 3 |
| 2025-02 | 160 |
| 2025-03 | 43 |
| 2025-04 | 119 |
| 2025-05 | 33 |
| 2025-06 | 62 |
| 2025-07 | 4 |
| 2025-08 | 60 |
| 2025-09 | 46 |
| 2025-10 | 169 |
| 2025-11 | 214 |
| 2025-12 | 322 |
| 2026-01 | 856 |
| 2026-02 | 1643 |
| 2026-03 | 1089 |
| 2026-04 | 994 |
| 2026-05 | 1576 |
| 2026-06 | 4100 |
| 2026-07 | 2114 |
| 2026-08 | 1472 |
| 2026-09 | 3425 |

## 6. Kode bahasa dari platform (seluruh dataset)

Ditandai bukan Indonesia hanya bila kode di luar ['id', 'in', 'jv', 'ms', 'qam', 'qct', 'qht', 'qme', 'qst', 'su', 'tl', 'un', 'und', 'zxx'] dan teks memuat minimal 3 kata.

| kode | tiktok |
|---|---|
| id | 17242 |
| un | 1993 |
| ms | 1275 |
| en | 549 |
| tr | 99 |
| es | 66 |
| tl | 63 |
| zh | 37 |
| it | 31 |
| ja | 28 |
| fr | 27 |
| pt | 25 |
| de | 19 |
| hi | 14 |
| so | 13 |
| az | 11 |
| pl | 11 |
| km | 10 |
| vi | 10 |
| sm | 9 |
| jv | 8 |
| sv | 8 |
| su | 8 |
| cs | 7 |
| hu | 7 |
| mt | 7 |
| uz | 6 |
| ny | 6 |
| nl | 4 |
| sk | 4 |
| ps | 4 |
| bn | 4 |
| ro | 3 |
| af | 3 |
| ha | 3 |
| da | 3 |
| ur | 3 |
| yo | 2 |
| ar | 2 |
| gl | 2 |
| lt | 2 |
| co | 2 |
| et | 2 |
| ig | 2 |
| cy | 2 |
| sl | 1 |
| sw | 1 |
| no | 1 |
| my | 1 |
| lv | 1 |
| sh | 1 |
| ku | 1 |
| mi | 1 |
| eo | 1 |
| xh | 1 |
| sq | 1 |
| mg | 1 |
| fy | 1 |
| th | 1 |

## 7. Kelengkapan kolom (persen kosong)

Kosong berbeda dengan nol: like_count = 0 dihitung terisi.

| kolom | tiktok |
|---|---|
| author_hash | 0% |
| text | 2% |
| created_at | 0% |
| parent_id | 1% |
| conversation_id | 0% |
| like_count | 0% |
| reply_count | 50% |
| share_count | 99% |
| view_count | 99% |
| language | 0% |

## 8. Relasi balasan

Record yang `parent_id`-nya tidak ada di dataset (induk tidak ikut terambil). Penting untuk menelusuri utas di RQ3.

| platform | punya parent_id | induk tidak ada di dataset |
|---|---|---|
| tiktok | 21497 | 0 |

## 9. Konsentrasi komentar per video

Komentar (comment/reply) yang eligible dikelompokkan per `conversation_id` (video). Konsentrasi tinggi berarti sampel didominasi beberapa video; penting untuk bias sampling (C5) dan untuk memilih sampel anotasi.

| platform | video berkomentar | komentar eligible | median/video | terbanyak | porsi 5 video teratas | porsi 10% video teratas |
|---|---|---|---|---|---|---|
| tiktok | 148 | 18636 | 84 | 850 | 16% | 38% |

## 10. Contoh baris eligible

Teks disamarkan seperti `data/sample/` (@mention diganti, dipotong 80 karakter).

| platform | item_type | text | created_at | like_count | hashtags |
|---|---|---|---|---|---|
| tiktok | post | #mayorteddyindrawijaya #mayorteddy #teddysky89 #teddy #fyp #tiktok #trending #xy… | 2024-10-13 | 565600 | mayorteddyindrawijaya mayorteddy teddysky89 teddy fyp tiktok trending xyzbca viral |
| tiktok | comment | keren banget bpk mayor tedy tetep semangat terus ya manis senyumnya ganteng lg | 2024-10-13 | 13 |  |
| tiktok | comment | kerenn pak ,.met mlm | 2024-10-13 | 16 |  |

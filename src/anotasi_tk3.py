"""Pipeline anotasi TK-3 (Codebook v2): workbook, kesepakatan, label emas.

Desain anotasi (lihat Codebook v2, bagian Prosedur anotasi):
    - Sampel emas 300 komentar dan 30 komentar pilot diambil dari
      data/processed/anotasi_tk3/sample_master.csv (strata = bulan, kolom batch).
    - Pilot: dikerjakan keempat annotator.
    - Batch A: Azzahra + Kania. Batch B: Clara + Nafia. Setiap komentar emas
      dilabeli dua orang, lalu semua ketidaksepakatan diadjudikasi.

Jalankan dari root repo:
    python -m src.anotasi_tk3 buat
    python -m src.anotasi_tk3 kesepakatan --fase pilot
    python -m src.anotasi_tk3 kesepakatan --fase utama
    python -m src.anotasi_tk3 gabung

Pilot ulang (bila pilot belum lolos kriteria lanjut):
    python -m src.anotasi_tk3 pilot-baru
    python -m src.anotasi_tk3 kesepakatan --fase pilot --folder data/processed/anotasi_tk3_v2/pilot2

Semua path punya nilai bawaan (lihat --help). Keluaran ada di
data/processed/anotasi_tk3_v2/ dan tidak ikut di-commit (.gitignore).
Hanya butuh openpyxl.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import random
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parents[1]
BAWAAN_SAMPEL = ROOT / "data/processed/anotasi_tk3/sample_master.csv"
BAWAAN_DATASET = ROOT / "data/processed/dataset_v05.csv"
BAWAAN_KELUARAN = ROOT / "data/processed/anotasi_tk3_v2"
BAWAAN_PASANGAN = ["A=Azzahra,Kania", "B=Clara,Nafia"]

VERSI_CODEBOOK = "v2.1"
URL_CODEBOOK = "https://claude.ai/artifact/Tq4RJKJ8eP2QnfJQSLu1MY"

# ---------------------------------------------------------------------------
# Skema label: satu-satunya sumber untuk dropdown, validasi, dan kappa.
# Harus sama persis dengan bagian "Workbook dan nilai dropdown" di codebook.
# ---------------------------------------------------------------------------
NILAI = {
    "relevansi": ["relevan", "tidak_relevan", "spam"],
    "sentimen": ["positif", "negatif", "netral"],
    "sikap": ["fan_culture", "kritik_substantif", "kritik_nonsubstantif", "lainnya"],
    "parasosial": ["ya", "tidak"],
    "penanda_pp": ["klaim_kedekatan", "membela_atas_nama", "kata_ganti_kolektif",
                   "panggilan_afektif", "sapaan"],
    "el_komunitas": ["ya", "tidak"],
    "el_afeksi": ["ya", "tidak"],
    "el_kontestasi": ["ya", "tidak"],
    "ironi": ["ya", "tidak"],
    "ragu": ["ya", "tidak"],
}
KOLOM_LABEL = list(NILAI)
KOLOM_EMAS = [k for k in KOLOM_LABEL if k != "ragu"]   # ragu = flag proses, bukan label emas
LAPIS2 = ["el_komunitas", "el_afeksi", "el_kontestasi"]
KOLOM_DITINJAU_SAAT_RAGU = ["relevansi", "sentimen", "sikap", "parasosial", "ironi"]
KOSONG = "(kosong)"

KOLOM_SHEET = ["no", "id_komentar", "teks", "konteks"] + KOLOM_LABEL + ["catatan", "status"]
HURUF = {nama: get_column_letter(i + 1) for i, nama in enumerate(KOLOM_SHEET)}
KOLOM_DIISI = KOLOM_LABEL + ["catatan"]

# Kolom ikut dihitung kappa hanya pada komentar yang memenuhi syarat ini menurut SEMUA annotator.
SYARAT_KAPPA = {
    "relevansi": lambda r: True,
    "sentimen": lambda r: r["relevansi"] == "relevan",
    "sikap": lambda r: r["relevansi"] == "relevan",
    "parasosial": lambda r: r["relevansi"] == "relevan",
    "ironi": lambda r: r["relevansi"] == "relevan",
    "penanda_pp": lambda r: r["relevansi"] == "relevan" and r["parasosial"] == "ya",
    "el_komunitas": lambda r: r["relevansi"] == "relevan" and r["sikap"] == "fan_culture",
    "el_afeksi": lambda r: r["relevansi"] == "relevan" and r["sikap"] == "fan_culture",
    "el_kontestasi": lambda r: r["relevansi"] == "relevan" and r["sikap"] == "fan_culture",
}
KETERANGAN_SYARAT = {
    "relevansi": "semua komentar", "sentimen": "semua relevan", "sikap": "semua relevan",
    "parasosial": "semua relevan", "ironi": "semua relevan",
    "penanda_pp": "semua parasosial = ya", "el_komunitas": "semua fan_culture",
    "el_afeksi": "semua fan_culture", "el_kontestasi": "semua fan_culture",
}

FONT = "Arial"
ISI = PatternFill("solid", fgColor="FFF2CC")
ABU = PatternFill("solid", fgColor="D9D9D9")
MERAH = PatternFill("solid", fgColor="F4CCCC")
KUNING = PatternFill("solid", fgColor="FFE599")
HIJAU = PatternFill("solid", fgColor="D9EAD3")
HEADER_TETAP = PatternFill("solid", fgColor="595959")
HEADER_ISI = PatternFill("solid", fgColor="1F4E79")
GARIS = Border(bottom=Side(style="thin", color="BFBFBF"))


# ---------------------------------------------------------------------------
# Utilitas
# ---------------------------------------------------------------------------
def gagal(pesan: str) -> None:
    print(f"GAGAL: {pesan}", file=sys.stderr)
    sys.exit(1)


def baca_csv(path: Path) -> list[dict]:
    if not path.exists():
        gagal(f"{path} tidak ditemukan. Jalankan perintah dari root repo atau beri path lengkap.")
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def urai_pasangan(teks: list[str]) -> dict[str, list[str]]:
    """['A=Azzahra,Kania', 'B=Clara,Nafia'] -> {'A': ['Azzahra', 'Kania'], ...}"""
    hasil = {}
    for t in teks:
        if "=" not in t:
            gagal(f"Format --pasangan salah: {t}. Contoh: A=Azzahra,Kania")
        batch, nama = t.split("=", 1)
        orang = [n.strip() for n in nama.split(",") if n.strip()]
        if len(orang) != 2:
            gagal(f"Batch {batch} harus punya tepat dua annotator, bukan {orang}.")
        hasil[batch.strip()] = orang
    semua = [n for o in hasil.values() for n in o]
    if len(set(semua)) != len(semua):
        gagal("Satu annotator tidak boleh berada di dua batch.")
    return hasil


def path_workbook(folder: Path, nama: str) -> Path:
    return folder / f"anotasi_{nama}.xlsx"


def cek_baris(r: dict) -> list[str]:
    """Logika yang sama dengan rumus kolom status di Excel."""
    v = {k: (r.get(k) or "") for k in KOLOM_DIISI}
    if not v["relevansi"]:
        return ["relevansi kosong"]
    isi_lain = [k for k in KOLOM_LABEL[1:] if k not in ("ironi", "ragu") and v[k]]
    if v["relevansi"] != "relevan":
        return [f"kosongkan {', '.join(isi_lain)}"] if isi_lain else []
    masalah = [f"{k} kosong" for k in ("sentimen", "sikap", "parasosial") if not v[k]]
    if v["parasosial"] == "ya" and not v["penanda_pp"]:
        masalah.append("penanda_pp kosong")
    if v["parasosial"] != "ya" and v["penanda_pp"]:
        masalah.append("kosongkan penanda_pp")
    if v["sikap"] == "fan_culture":
        masalah += [f"{k} kosong" for k in LAPIS2 if not v[k]]
    elif any(v[k] for k in LAPIS2):
        masalah.append("kosongkan lapis 2")
    if v["ragu"] == "ya" and not v["catatan"]:
        masalah.append("alasan ragu kosong")
    for k in KOLOM_LABEL:
        if v[k] and v[k] not in NILAI[k]:
            masalah.append(f"nilai {k} tidak dikenal: {v[k]}")
    return masalah


# ---------------------------------------------------------------------------
# buat
# ---------------------------------------------------------------------------
RUMUS_STATUS = (
    '=IF({E}{r}="","belum: relevansi",'
    'IF({E}{r}<>"relevan",IF(COUNTA({F}{r}:{L}{r})>0,"KOSONGKAN kolom sentimen s.d. el_kontestasi","lengkap"),'
    'IF(OR({F}{r}="",{G}{r}="",{H}{r}=""),"belum: sentimen/sikap/parasosial",'
    'IF(AND({H}{r}="ya",{I}{r}=""),"belum: penanda_pp",'
    'IF(AND({H}{r}<>"ya",{I}{r}<>""),"KOSONGKAN penanda_pp",'
    'IF(AND({G}{r}="fan_culture",COUNTA({J}{r}:{L}{r})<3),"belum: lapis 2",'
    'IF(AND({G}{r}<>"fan_culture",COUNTA({J}{r}:{L}{r})>0),"KOSONGKAN lapis 2",'
    'IF(AND({N}{r}="ya",{O}{r}=""),"belum: alasan ragu","lengkap"))))))))'
)
HURUF_RUMUS = {"E": HURUF["relevansi"], "F": HURUF["sentimen"], "G": HURUF["sikap"],
               "H": HURUF["parasosial"], "I": HURUF["penanda_pp"], "J": HURUF["el_komunitas"],
               "L": HURUF["el_kontestasi"], "N": HURUF["ragu"], "O": HURUF["catatan"]}


def tulis_sheet_anotasi(ws, baris: list[dict]) -> None:
    akhir = len(baris) + 1
    h = HURUF
    lebar = {"no": 5, "id_komentar": 22, "teks": 60, "konteks": 40, "relevansi": 14,
             "sentimen": 11, "sikap": 21, "parasosial": 11, "penanda_pp": 20,
             "el_komunitas": 15, "el_afeksi": 11, "el_kontestasi": 15, "ironi": 8,
             "ragu": 8, "catatan": 34, "status": 34}
    for j, nama in enumerate(KOLOM_SHEET, start=1):
        c = ws.cell(row=1, column=j, value=nama)
        c.font = Font(name=FONT, bold=True, color="FFFFFF")
        c.fill = HEADER_ISI if nama in KOLOM_DIISI else HEADER_TETAP
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(j)].width = lebar[nama]
    ws.row_dimensions[1].height = 30

    for i, b in enumerate(baris, start=2):
        nilai = {"no": i - 1, "id_komentar": b["id_komentar"], "teks": b["teks"],
                 "konteks": b["konteks"], "ironi": "tidak", "ragu": "tidak"}
        for j, nama in enumerate(KOLOM_SHEET, start=1):
            c = ws.cell(row=i, column=j)
            c.value = RUMUS_STATUS.format(r=i, **HURUF_RUMUS) if nama == "status" else nilai.get(nama)
            c.font = Font(name=FONT, size=10)
            c.border = GARIS
            c.alignment = Alignment(vertical="top", wrap_text=nama in ("teks", "konteks", "catatan", "status"))
            if nama in KOLOM_DIISI:
                c.fill = ISI
        ws.cell(row=i, column=2).number_format = "@"   # ID TikTok tetap teks, bukan notasi ilmiah

    for nama in KOLOM_LABEL:
        dv = DataValidation(type="list", formula1='"' + ",".join(NILAI[nama]) + '"',
                            allow_blank=True, showErrorMessage=True, errorTitle="Nilai tidak valid",
                            error=f"Pilih salah satu: {', '.join(NILAI[nama])}")
        ws.add_data_validation(dv)
        dv.add(f"{h[nama]}2:{h[nama]}{akhir}")

    bukan_relevan = f'AND(${h["relevansi"]}2<>"",${h["relevansi"]}2<>"relevan")'
    ws.conditional_formatting.add(f"{h['sentimen']}2:{h['parasosial']}{akhir}",
                                  FormulaRule(formula=[bukan_relevan], fill=ABU))
    ws.conditional_formatting.add(f"{h['penanda_pp']}2:{h['penanda_pp']}{akhir}",
                                  FormulaRule(formula=[f'OR({bukan_relevan},${h["parasosial"]}2<>"ya")'], fill=ABU))
    ws.conditional_formatting.add(f"{h['el_komunitas']}2:{h['el_kontestasi']}{akhir}",
                                  FormulaRule(formula=[f'OR({bukan_relevan},${h["sikap"]}2<>"fan_culture")'], fill=ABU))
    s = h["status"]
    ws.conditional_formatting.add(f"{s}2:{s}{akhir}", FormulaRule(formula=[f'LEFT(${s}2,9)="KOSONGKAN"'], fill=MERAH))
    ws.conditional_formatting.add(f"{s}2:{s}{akhir}", FormulaRule(formula=[f'LEFT(${s}2,5)="belum"'], fill=KUNING))
    ws.conditional_formatting.add(f"{s}2:{s}{akhir}", FormulaRule(formula=[f'${s}2="lengkap"'], fill=HIJAU))
    ws.freeze_panes = "E2"
    ws.auto_filter.ref = f"A1:{s}{akhir}"


def tulis_petunjuk(ws, nama: str, batch: str, n_pilot: int, n_utama: int | None, seed: int, putaran: str = "") -> None:
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 95
    judul = f"Anotasi TK-3 \u00b7 {nama} ({putaran})" if putaran else f"Anotasi TK-3 \u00b7 {nama} (batch {batch})"
    ws.cell(row=1, column=1, value=judul).font = Font(name=FONT, size=14, bold=True)
    r = 3
    for k, v in [("Annotator", nama), ("Batch utama" if not putaran else "Putaran", batch if not putaran else putaran), ("Versi codebook", VERSI_CODEBOOK),
                 ("Codebook", URL_CODEBOOK), ("Dibuat", dt.date.today().isoformat()), ("Seed", str(seed))]:
        ws.cell(row=r, column=1, value=k).font = Font(name=FONT, bold=True)
        ws.cell(row=r, column=2, value=v).font = Font(name=FONT)
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="Progres").font = Font(name=FONT, size=12, bold=True)
    r += 1
    for sheet, n in (("Pilot", n_pilot), ("Utama", n_utama)):
        if n is None:
            continue
        ws.cell(row=r, column=1, value=f"{sheet}: lengkap").font = Font(name=FONT, bold=True)
        st = HURUF["status"]
        ws.cell(row=r, column=2, value=f'=COUNTIF({sheet}!{st}2:{st}{n + 1},"lengkap")&" dari {n} komentar"').font = Font(name=FONT)
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="Cara mengisi").font = Font(name=FONT, size=12, bold=True)
    r += 1
    for i, t in enumerate([
        ("Workbook ini hanya berisi pilot putaran ulang. Kerjakan dengan codebook " + VERSI_CODEBOOK + "."
         if n_utama is None else "Kerjakan sheet Pilot dulu. Sheet Utama baru dikerjakan setelah codebook dikunci."),
        "Isi hanya kolom berwarna kuning (header biru). Kolom abu-abu tidak berlaku untuk baris itu.",
        "Urutan: relevansi, lalu sentimen, sikap, parasosial. Lapis 2 hanya bila sikap = fan_culture.",
        "ironi dan ragu sudah terisi 'tidak'. Ubah ke 'ya' hanya bila berlaku; ragu = ya wajib diberi alasan di catatan.",
        "Kolom status harus 'lengkap' (hijau) di semua baris. Kuning = ada yang kurang, merah = ada yang harus dikosongkan.",
        "Kerjakan sendiri: jangan membuka file anggota lain dan jangan membahas komentar tertentu sebelum adjudikasi.",
        "Paling banyak sekitar 50 komentar per sesi, lalu istirahat.",
        "Jangan mengubah, mengurutkan ulang permanen, atau menghapus kolom no, id_komentar, teks, konteks.",
    ], start=1):
        ws.cell(row=r, column=1, value=f"{i}.").font = Font(name=FONT)
        c = ws.cell(row=r, column=2, value=t)
        c.font = Font(name=FONT)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="Kode catatan").font = Font(name=FONT, size=12, bold=True)
    r += 1
    for kode, arti in [("#emoji", "Komentar hanya berisi emoji"),
                       ("#bahasa", "Dominan berbahasa asing atau daerah"),
                       ("#konteks", "Maknanya baru jelas setelah membaca caption video"),
                       ("#antifandom", "Tampak berasal dari anti-penggemar"),
                       ("#produksi", "Menyebut pembuatan atau konsumsi konten turunan"),
                       ("#pp", "Penanda parasosial lain di luar penanda_pp")]:
        ws.cell(row=r, column=1, value=kode).font = Font(name=FONT)
        ws.cell(row=r, column=2, value=arti).font = Font(name=FONT)
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="Contoh pengisian").font = Font(name=FONT, size=12, bold=True)
    r += 1
    ws.cell(row=r, column=1, value="Ilustratif, bukan komentar asli.").font = Font(name=FONT, italic=True, color="595959")
    r += 1
    for k, v in {"teks": "beliau nggak gitu orangnya, yang nyinyir coba baca aturannya dulu",
                 "relevansi": "relevan", "sentimen": "negatif", "sikap": "fan_culture",
                 "parasosial": "ya", "penanda_pp": "membela_atas_nama", "el_komunitas": "tidak",
                 "el_afeksi": "tidak", "el_kontestasi": "ya", "ironi": "tidak", "ragu": "tidak",
                 "catatan": KOSONG}.items():
        ws.cell(row=r, column=1, value=k).font = Font(name=FONT, bold=True)
        ws.cell(row=r, column=2, value=v).font = Font(name=FONT)
        r += 1
    c = ws.cell(row=r, column=2, value=(
        "Sentimen negatif karena nadanya menyerang pengkritik; sikap tetap fan_culture karena membela figur. "
        "Membela seakan mengenal figur = membela_atas_nama; membantah pengkritik = el_kontestasi."))
    c.font = Font(name=FONT, italic=True, color="595959")
    c.alignment = Alignment(wrap_text=True)


def cmd_buat(args) -> None:
    pasangan = urai_pasangan(args.pasangan)
    out = Path(args.keluaran)
    sampel = baca_csv(Path(args.sampel))
    for k in ("item_id", "parent_id", "bulan", "batch"):
        if k not in sampel[0]:
            gagal(f"{args.sampel} tidak punya kolom {k}.")
    batch_ada = Counter(s["batch"] for s in sampel)
    if set(batch_ada) - {"pilot"} != set(pasangan):
        gagal(f"Batch di sampel {sorted(batch_ada)} tidak cocok dengan --pasangan {sorted(pasangan)}.")
    dup = [i for i, c in Counter(s["item_id"] for s in sampel).items() if c > 1]
    if dup:
        gagal(f"item_id ganda di sampel: {dup[:5]}")

    # Teks komentar dan caption video induk dari dataset
    dataset = {}
    with open(args.dataset, newline="", encoding="utf-8-sig") as f:
        for d in csv.DictReader(f):
            dataset[d["item_id"]] = d
    data = []
    hilang, tidak_eligible = [], []
    for s in sampel:
        d = dataset.get(s["item_id"])
        if not d:
            hilang.append(s["item_id"])
            continue
        if str(d.get("eligible", "True")).lower() != "true":
            tidak_eligible.append(s["item_id"])
        induk = dataset.get(d["parent_id"] or s["parent_id"], {})
        data.append({"id_komentar": s["item_id"], "teks": d["text"],
                     "konteks": induk.get("text", "") or "(video tanpa caption)", "batch": s["batch"],
                     "bulan": s["bulan"], "bobot": s.get("bobot", "")})
    if hilang:
        gagal(f"{len(hilang)} item_id sampel tidak ada di {args.dataset}, mis. {hilang[:5]}")
    if tidak_eligible:
        print(f"Peringatan: {len(tidak_eligible)} komentar sampel ditandai tidak eligible di dataset.")
    tanpa_konteks = sum(1 for d in data if d["konteks"] == "(video tanpa caption)")
    if tanpa_konteks:
        print(f"Catatan: {tanpa_konteks} komentar berasal dari video tanpa caption.")

    if out.exists() and any(out.glob("anotasi_*.xlsx")) and not args.timpa:
        gagal(f"{out} sudah berisi workbook. Workbook yang mungkin sudah diisi tidak ditimpa; "
              "pakai --timpa bila memang ingin membuat ulang.")
    out.mkdir(parents=True, exist_ok=True)

    pilot = [d for d in data if d["batch"] == "pilot"]
    penugasan = []
    for batch, orang in pasangan.items():
        utama = [d for d in data if d["batch"] == batch]
        for nama in orang:
            p = pilot[:]
            u = utama[:]
            random.Random(f"{args.seed}-pilot-{nama}").shuffle(p)   # urutan diacak per annotator
            random.Random(f"{args.seed}-utama-{nama}").shuffle(u)
            wb = Workbook()
            wb.active.title = "Petunjuk"
            tulis_petunjuk(wb.active, nama, batch, len(p), len(u), args.seed)
            tulis_sheet_anotasi(wb.create_sheet("Pilot"), p)
            tulis_sheet_anotasi(wb.create_sheet("Utama"), u)
            wb.save(path_workbook(out, nama))
            print(f"anotasi_{nama}.xlsx: Pilot {len(p)} + Utama {len(u)} (batch {batch})")
    semua = [n for o in pasangan.values() for n in o]
    for d in data:
        anot = semua if d["batch"] == "pilot" else pasangan[d["batch"]]
        penugasan.append({"id_komentar": d["id_komentar"], "bulan": d["bulan"], "bobot": d["bobot"],
                          "fase": "pilot" if d["batch"] == "pilot" else "utama",
                          "batch": d["batch"], "annotator": ";".join(anot)})
    with open(out / "penugasan.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(penugasan[0]))
        w.writeheader()
        w.writerows(penugasan)
    print(f"Ditulis ke {out}. Bagikan tiap workbook hanya ke pemiliknya.")



def alokasi_proporsional(jumlah_per_strata: dict[str, int], n: int) -> dict[str, int]:
    """Metode sisa terbesar (Hamilton): proporsional per strata, total tepat n."""
    total = sum(jumlah_per_strata.values())
    kuota = {s: n * c / total for s, c in jumlah_per_strata.items()}
    hasil = {s: int(q) for s, q in kuota.items()}
    sisa = n - sum(hasil.values())
    for s in sorted(kuota, key=lambda s: (kuota[s] - hasil[s], s), reverse=True)[:sisa]:
        hasil[s] += 1
    return hasil


def cmd_pilot_baru(args) -> None:
    """Ambil komentar pilot baru dari populasi yang sama dengan sampel emas."""
    pasangan = urai_pasangan(args.pasangan)
    semua = [n for o in pasangan.values() for n in o]
    out = Path(args.keluaran)
    if out.exists() and any(out.glob("anotasi_*.xlsx")) and not args.timpa:
        gagal(f"{out} sudah berisi workbook; pakai --timpa bila memang ingin membuat ulang.")

    kecuali = {s["item_id"] for s in baca_csv(Path(args.sampel))}
    for extra in args.kecualikan or []:
        kecuali |= {r.get("id_komentar") or r.get("item_id") for r in baca_csv(Path(extra))}
    dataset = {}
    with open(args.dataset, newline="", encoding="utf-8-sig") as f:
        for d in csv.DictReader(f):
            dataset[d["item_id"]] = d
    # Kerangka sampel = komentar eligible, sama dengan N_populasi di sample_master.csv
    kerangka = defaultdict(list)
    for d in dataset.values():
        if d["item_type"] == "comment" and d["eligible"] == "True":
            kerangka[d["created_at"][:7]].append(d)
    kuota = alokasi_proporsional({b: len(v) for b, v in kerangka.items()}, args.n)
    rng = random.Random(args.seed)
    pilih = []
    for bulan in sorted(kerangka):
        calon = sorted((d for d in kerangka[bulan] if d["item_id"] not in kecuali), key=lambda d: d["item_id"])
        rng.shuffle(calon)
        if len(calon) < kuota[bulan]:
            gagal(f"Bulan {bulan} tidak punya cukup komentar baru.")
        pilih += calon[:kuota[bulan]]

    data = [{"id_komentar": d["item_id"], "teks": d["text"], "bulan": d["created_at"][:7],
             "konteks": dataset.get(d["parent_id"], {}).get("text", "") or "(video tanpa caption)"} for d in pilih]
    out.mkdir(parents=True, exist_ok=True)
    putaran = args.nama_putaran
    for nama in semua:
        p = data[:]
        random.Random(f"{args.seed}-{putaran}-{nama}").shuffle(p)
        wb = Workbook()
        wb.active.title = "Petunjuk"
        batch = next(b for b, o in pasangan.items() if nama in o)
        tulis_petunjuk(wb.active, nama, batch, len(p), None, args.seed, putaran=putaran)
        tulis_sheet_anotasi(wb.create_sheet("Pilot"), p)
        wb.save(path_workbook(out, nama))
        print(f"anotasi_{nama}.xlsx: Pilot {len(p)} ({putaran})")
    with open(out / "penugasan.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id_komentar", "bulan", "bobot", "fase", "batch", "annotator"])
        w.writeheader()
        for d in data:
            w.writerow({"id_komentar": d["id_komentar"], "bulan": d["bulan"], "bobot": "", "fase": "pilot",
                        "batch": putaran, "annotator": ";".join(semua)})
    print(f"{len(data)} komentar dari {sum(1 for b in kuota if kuota[b])} bulan, di luar {len(kecuali)} komentar "
          f"yang sudah pernah dipakai. Ditulis ke {out}.")

# ---------------------------------------------------------------------------
# Membaca hasil anotasi
# ---------------------------------------------------------------------------
def baca_anotasi(path: Path, sheet: str) -> dict[str, dict]:
    if not path.exists():
        gagal(f"{path} tidak ditemukan.")
    wb = load_workbook(path)
    if sheet not in wb.sheetnames:
        gagal(f"{path.name} tidak punya sheet {sheet}.")
    ws = wb[sheet]
    header = [c.value for c in ws[1]]
    for k in ["id_komentar", "teks", "konteks"] + KOLOM_DIISI:
        if k not in header:
            gagal(f"{path.name}/{sheet} tidak punya kolom {k}. Jangan mengubah header.")
    idx = {k: header.index(k) for k in header if k}
    hasil = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[idx["id_komentar"]] in (None, ""):
            continue
        r = {k: ("" if row[idx[k]] is None else str(row[idx[k]]).strip()) for k in idx if k != "status"}
        hasil[r["id_komentar"]] = r
    return hasil


def muat_semua(folder: Path, sheet: str) -> tuple[list[dict], dict[str, dict[str, dict]]]:
    penugasan = baca_csv(folder / "penugasan.csv")
    nama = sorted({n for p in penugasan for n in p["annotator"].split(";")})
    return penugasan, {n: baca_anotasi(path_workbook(folder, n), sheet) for n in nama}


def periksa_kelengkapan(data: dict[str, dict[str, dict]], tugas: dict[str, list[str]]) -> int:
    total = 0
    for nama, ids in tugas.items():
        salah = [(i, cek_baris(data[nama][i])) for i in ids if i in data[nama] and cek_baris(data[nama][i])]
        hilang = [i for i in ids if i not in data[nama]]
        for i in hilang[:5]:
            print(f"  {nama}: id {i} tidak ditemukan")
        for i, m in salah[:10]:
            print(f"  {nama}: {i}: {'; '.join(m)}")
        if len(salah) > 10:
            print(f"  {nama}: ... dan {len(salah) - 10} baris lain")
        total += len(salah) + len(hilang)
    return total


def cohen_kappa(a: list[str], b: list[str]) -> tuple[float | None, float]:
    n = len(a)
    if n == 0:
        return None, float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return (None if pe >= 1 else (po - pe) / (1 - pe)), po


def fleiss_kappa(label_per_item: list[list[str]]) -> float | None:
    """Fleiss' kappa; setiap item dilabeli jumlah annotator yang sama."""
    if not label_per_item:
        return None
    m = len(label_per_item[0])
    n_item = len(label_per_item)
    kategori = sorted({x for item in label_per_item for x in item})
    pi = [(sum(c * c for c in Counter(item).values()) - m) / (m * (m - 1)) for item in label_per_item]
    p_bar = sum(pi) / n_item
    pj = [sum(item.count(k) for item in label_per_item) / (n_item * m) for k in kategori]
    pe = sum(p * p for p in pj)
    return None if pe >= 1 else (p_bar - pe) / (1 - pe)


def fmt(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.2f}"


# ---------------------------------------------------------------------------
# kesepakatan
# ---------------------------------------------------------------------------
def cmd_kesepakatan(args) -> None:
    folder = Path(args.folder)
    sheet = "Pilot" if args.fase == "pilot" else "Utama"
    penugasan, data = muat_semua(folder, sheet)
    tugas_item = [p for p in penugasan if p["fase"] == args.fase]
    tugas = defaultdict(list)
    for p in tugas_item:
        for n in p["annotator"].split(";"):
            tugas[n].append(p["id_komentar"])

    masalah = periksa_kelengkapan(data, tugas)
    if masalah and not args.paksa:
        gagal(f"{masalah} baris belum lengkap atau tidak konsisten. Perbaiki dulu, "
              "atau jalankan dengan --paksa untuk hasil sementara.")

    # Kelompok pembanding: di pilot semua pasangan annotator, di utama tiap batch.
    grup = defaultdict(list)                     # (A, B) -> [id]
    for p in tugas_item:
        orang = p["annotator"].split(";")
        for a, b in combinations(sorted(orang), 2):
            grup[(a, b)].append(p["id_komentar"])
    laporan = []
    for (a, b), ids in sorted(grup.items()):
        for k in KOLOM_EMAS:
            pas = [i for i in ids if i in data[a] and i in data[b]
                   and SYARAT_KAPPA[k](data[a][i]) and SYARAT_KAPPA[k](data[b][i])]
            kap, po = cohen_kappa([data[a][i][k] for i in pas], [data[b][i][k] for i in pas])
            cnt = Counter([data[a][i][k] for i in pas] + [data[b][i][k] for i in pas])
            prev = ", ".join(f"{lab} {cnt[lab] / (2 * len(pas)):.0%}" for lab in NILAI[k] if cnt[lab]) if pas else "-"
            laporan.append({"fase": args.fase, "pembanding": f"{a} vs {b}", "kolom": k,
                            "syarat": KETERANGAN_SYARAT[k], "n": len(pas),
                            "persen_sepakat": f"{po:.3f}" if pas else "",
                            "kappa": "" if kap is None else f"{kap:.3f}", "prevalensi": prev})

    if args.fase == "pilot":
        nama = sorted(tugas)
        ids = [p["id_komentar"] for p in tugas_item]
        for k in KOLOM_EMAS:
            pas = [i for i in ids if all(i in data[n] and SYARAT_KAPPA[k](data[n][i]) for n in nama)]
            fk = fleiss_kappa([[data[n][i][k] for n in nama] for i in pas])
            laporan.append({"fase": "pilot", "pembanding": "Fleiss (semua)", "kolom": k,
                            "syarat": KETERANGAN_SYARAT[k], "n": len(pas), "persen_sepakat": "",
                            "kappa": "" if fk is None else f"{fk:.3f}", "prevalensi": ""})

    pembanding = list(dict.fromkeys(r["pembanding"] for r in laporan))
    tabel = {(r["pembanding"], r["kolom"]): r for r in laporan}
    print(f"\nKappa fase {args.fase} (n = jumlah komentar yang memenuhi syarat kolom)\n")
    print(f"{'kolom':<15}" + "".join(f"{p:>24}" for p in pembanding))
    for k in KOLOM_EMAS:
        sel = []
        for p in pembanding:
            r = tabel[(p, k)]
            sel.append(f"{fmt(float(r['kappa'])) if r['kappa'] else 'n/a'} (n={r['n']})")
        print(f"{k:<15}" + "".join(f"{s:>24}" for s in sel))
    with open(folder / f"kesepakatan_{args.fase}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(laporan[0]))
        w.writeheader()
        w.writerows(laporan)

    utama_pas = [p for p in pembanding if p != "Fleiss (semua)"]
    if args.fase == "pilot":
        kunci = [(p, k) for p in utama_pas for k in ("sentimen", "sikap")]
        # yang menentukan: pasangan kerja (satu batch), bukan pasangan lintas batch
        kerja = {" vs ".join(sorted(o)) for o in (pasangan_dari(penugasan) or urai_pasangan(args.pasangan).values())}
        kunci = [(p, k) for p, k in kunci if p in kerja]
        lolos = all(tabel[x]["kappa"] and float(tabel[x]["kappa"]) >= 0.60 for x in kunci)
        print("\nKriteria lanjut (kappa sentimen dan sikap >= 0,60 pada kedua pasangan kerja): "
              + ("TERPENUHI" if lolos else "BELUM"))
    rendah = sorted({r["kolom"] for r in laporan if r["kappa"] and float(r["kappa"]) < 0.40})
    if rendah:
        print("Kolom dengan kappa < 0,40 di salah satu pembanding: " + ", ".join(rendah))
    print("Kappa dihitung dari label sebelum adjudikasi. Prevalensi ada di kesepakatan_<fase>.csv.")

    # Lembar adjudikasi: satu baris per komentar x kolom yang perlu diputuskan.
    semua_nama = sorted(tugas)
    rows = []
    for p in tugas_item:
        i, orang = p["id_komentar"], p["annotator"].split(";")
        label = {n: data[n].get(i, {}) for n in orang}
        ragu = any(l.get("ragu") == "ya" for l in label.values())
        for k in KOLOM_EMAS:
            nilai = {n: label[n].get(k, "") for n in orang}
            if len(set(nilai.values())) > 1:
                rows.append({"id": i, "batch": p["batch"], "alasan": "beda", "kolom": k, "label": nilai, "final": ""})
            elif ragu and k in KOLOM_DITINJAU_SAAT_RAGU:
                v = next(iter(nilai.values()))
                rows.append({"id": i, "batch": p["batch"], "alasan": "ragu", "kolom": k, "label": nilai,
                             "final": v or KOSONG})
    tulis_adjudikasi(folder / f"adjudikasi_{args.fase}.xlsx", rows, data, semua_nama)
    n_beda = sum(1 for r in rows if r["alasan"] == "beda")
    print(f"\nadjudikasi_{args.fase}.xlsx: {n_beda} ketidaksepakatan dan {len(rows) - n_beda} baris ragu.")


def pasangan_dari(penugasan: list[dict]) -> list[list[str]]:
    return sorted({tuple(p["annotator"].split(";")) for p in penugasan if p["fase"] == "utama"})


def tulis_adjudikasi(path: Path, rows: list[dict], data, semua_nama: list[str]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Adjudikasi"
    kolom = (["id_komentar", "batch", "teks", "konteks", "alasan", "kolom"]
             + [f"label_{n}" for n in semua_nama] + ["catatan_annotator", "label_final", "dasar_keputusan"])
    lebar = [22, 7, 50, 30, 8, 15] + [16] * len(semua_nama) + [36, 20, 34]
    for j, (nama, w) in enumerate(zip(kolom, lebar), start=1):
        c = ws.cell(row=1, column=j, value=nama)
        c.font = Font(name=FONT, bold=True, color="FFFFFF")
        c.fill = HEADER_ISI if nama in ("label_final", "dasar_keputusan") else HEADER_TETAP
        c.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(j)].width = w
    j_final = kolom.index("label_final") + 1
    rows = sorted(rows, key=lambda r: (r["batch"], r["id"], KOLOM_EMAS.index(r["kolom"])))
    for r_i, r in enumerate(rows, start=2):
        src = next((data[n][r["id"]] for n in r["label"] if r["id"] in data[n]), {})
        catatan = " | ".join(f"{n}: {data[n][r['id']]['catatan']}" for n in r["label"]
                             if r["id"] in data[n] and data[n][r["id"]].get("catatan"))
        vals = ([r["id"], r["batch"], src.get("teks", ""), src.get("konteks", ""), r["alasan"], r["kolom"]]
                + [(r["label"][n] or KOSONG) if n in r["label"] else "" for n in semua_nama]
                + [catatan, r["final"], ""])
        for j, v in enumerate(vals, start=1):
            c = ws.cell(row=r_i, column=j, value=v)
            c.font = Font(name=FONT, size=10)
            c.alignment = Alignment(wrap_text=kolom[j - 1] in ("teks", "konteks", "catatan_annotator", "dasar_keputusan"),
                                    vertical="top")
            c.border = GARIS
            if j >= j_final:
                c.fill = ISI
        ws.cell(row=r_i, column=1).number_format = "@"
        dv = DataValidation(type="list", formula1='"' + ",".join(NILAI[r["kolom"]] + [KOSONG]) + '"',
                            allow_blank=True, showErrorMessage=True)
        ws.add_data_validation(dv)
        dv.add(ws.cell(row=r_i, column=j_final).coordinate)
    if rows:
        hf = get_column_letter(j_final)
        ws.conditional_formatting.add(f"{hf}2:{hf}{len(rows) + 1}", FormulaRule(formula=[f'${hf}2=""'], fill=KUNING))
        ws.auto_filter.ref = f"A1:{get_column_letter(len(kolom))}{len(rows) + 1}"
    ws.freeze_panes = "G2"

    pet = wb.create_sheet("Petunjuk")
    pet.column_dimensions["A"].width = 110
    for n, t in enumerate([
        "Satu baris = satu kolom pada satu komentar yang perlu diputuskan.",
        "alasan 'beda': annotator berbeda. label_final masih kosong (kuning) dan wajib diisi.",
        "alasan 'ragu': ada annotator yang mencentang ragu. label_final sudah terisi label saat ini; ubah bila perlu.",
        f"Pilih {KOSONG} bila kolom itu harus kosong (mis. lapis 2 ketika sikap final bukan fan_culture).",
        "Putuskan relevansi dan sikap lebih dulu, karena keduanya menentukan kolom lain.",
        "Pasangan batch berdiskusi; bila tetap berbeda, anggota dari batch lain memutuskan. Tulis alasannya di dasar_keputusan.",
        "Untuk fase utama, setelah selesai jalankan: python -m src.anotasi_tk3 gabung",
    ], start=1):
        pet.cell(row=n, column=1, value=t).font = Font(name=FONT)
    wb.save(path)


# ---------------------------------------------------------------------------
# gabung
# ---------------------------------------------------------------------------
def cmd_gabung(args) -> None:
    folder = Path(args.folder)
    penugasan, data = muat_semua(folder, "Utama")
    adj_path = Path(args.adjudikasi) if args.adjudikasi else folder / "adjudikasi_utama.xlsx"

    putusan = defaultdict(dict)
    if adj_path.exists():
        ws = load_workbook(adj_path)["Adjudikasi"]
        header = [c.value for c in ws[1]]
        ix = {k: header.index(k) for k in ("id_komentar", "kolom", "label_final")}
        kosong_final = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row[ix["id_komentar"]]:
                continue
            i, k = str(row[ix["id_komentar"]]), row[ix["kolom"]]
            final = "" if row[ix["label_final"]] is None else str(row[ix["label_final"]]).strip()
            if not final:
                kosong_final.append(f"{i}/{k}")
                continue
            putusan[i][k] = "" if final == KOSONG else final
        if kosong_final:
            gagal(f"{len(kosong_final)} label_final belum diisi di {adj_path.name}, mis. {kosong_final[:5]}")
    else:
        print(f"Peringatan: {adj_path.name} tidak ada; hanya komentar yang disepakati yang bisa digabung.")

    emas, error = [], []
    for p in penugasan:
        if p["fase"] != "utama":
            continue
        i, orang = p["id_komentar"], p["annotator"].split(";")
        label = [data[n].get(i) for n in orang]
        if not all(label):
            error.append(f"{i}: tidak ditemukan di workbook {[n for n, l in zip(orang, label) if not l]}")
            continue
        base = {k: label[0][k] if len({l[k] for l in label}) == 1 else None for k in KOLOM_EMAS}
        base.update(putusan.get(i, {}))
        belum = [k for k, v in base.items() if v is None]
        if belum:
            error.append(f"{i}: beda pada {', '.join(belum)} tetapi belum diadjudikasi")
            continue
        m = cek_baris(dict(base, ragu="tidak", catatan="-"))
        if m:
            error.append(f"{i}: label akhir tidak konsisten ({'; '.join(m)})")
            continue
        catatan = " | ".join(f"{n}: {l['catatan']}" for n, l in zip(orang, label) if l["catatan"])
        emas.append({"id_komentar": i, "bulan": p["bulan"], "bobot": p["bobot"], "batch": p["batch"],
                     "teks": label[0]["teks"], **base,
                     "diadjudikasi": "ya" if i in putusan else "tidak", "catatan": catatan})

    if error:
        for e in error[:20]:
            print("  " + e)
        gagal(f"{len(error)} komentar belum bisa digabung.")
    kolom = ["id_komentar", "bulan", "bobot", "batch", "teks"] + KOLOM_EMAS + ["diadjudikasi", "catatan"]
    with open(folder / "label_emas.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=kolom)
        w.writeheader()
        w.writerows(emas)
    rel = [e for e in emas if e["relevansi"] == "relevan"]
    print(f"label_emas.csv: {len(emas)} komentar ({len(rel)} relevan). Kolom bobot dipakai untuk estimasi berbobot.")
    print("Sikap: " + ", ".join(f"{k} {v}" for k, v in Counter(e["sikap"] for e in rel).most_common()))
    print("Sentimen: " + ", ".join(f"{k} {v}" for k, v in Counter(e["sentimen"] for e in rel).most_common()))


# ---------------------------------------------------------------------------
def main() -> None:
    p = argparse.ArgumentParser(description="Pipeline anotasi TK-3 (Codebook v2). Jalankan dari root repo.")
    sub = p.add_subparsers(dest="perintah", required=True)

    b = sub.add_parser("buat", help="buat workbook per annotator dari sample_master.csv")
    b.add_argument("--sampel", default=str(BAWAAN_SAMPEL))
    b.add_argument("--dataset", default=str(BAWAAN_DATASET))
    b.add_argument("--keluaran", default=str(BAWAAN_KELUARAN))
    b.add_argument("--pasangan", nargs="+", default=BAWAAN_PASANGAN, help="mis. A=Azzahra,Kania B=Clara,Nafia")
    b.add_argument("--seed", type=int, default=2026)
    b.add_argument("--timpa", action="store_true", help="timpa workbook yang sudah ada")

    k = sub.add_parser("kesepakatan", help="hitung kappa dan buat lembar adjudikasi")
    k.add_argument("--fase", choices=["pilot", "utama"], required=True)
    k.add_argument("--folder", default=str(BAWAAN_KELUARAN))
    k.add_argument("--paksa", action="store_true", help="tetap hitung walau ada baris belum lengkap")
    k.add_argument("--pasangan", nargs="+", default=BAWAAN_PASANGAN,
                   help="pasangan kerja untuk kriteria pilot bila folder tidak punya fase utama")

    g = sub.add_parser("gabung", help="buat label_emas.csv dari batch utama + adjudikasi")
    g.add_argument("--folder", default=str(BAWAAN_KELUARAN))
    g.add_argument("--adjudikasi", help="bawaan: <folder>/adjudikasi_utama.xlsx")

    pb = sub.add_parser("pilot-baru", help="workbook pilot ulang dengan komentar baru dari dataset")
    pb.add_argument("--sampel", default=str(BAWAAN_SAMPEL), help="sampel emas + pilot lama, dikecualikan")
    pb.add_argument("--kecualikan", nargs="*", help="penugasan.csv pilot ulang sebelumnya, juga dikecualikan")
    pb.add_argument("--dataset", default=str(BAWAAN_DATASET))
    pb.add_argument("--keluaran", default=str(BAWAAN_KELUARAN / "pilot2"))
    pb.add_argument("--nama-putaran", default="pilot2")
    pb.add_argument("--n", type=int, default=30)
    pb.add_argument("--pasangan", nargs="+", default=BAWAAN_PASANGAN)
    pb.add_argument("--seed", type=int, default=2027)
    pb.add_argument("--timpa", action="store_true")

    args = p.parse_args()
    {"buat": cmd_buat, "kesepakatan": cmd_kesepakatan, "gabung": cmd_gabung,
     "pilot-baru": cmd_pilot_baru}[args.perintah](args)


if __name__ == "__main__":
    main()

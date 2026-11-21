"""Uji paritas: aturan naskah di web (web/naskah.js) harus identik dengan pipeline.susun.cek_naskah,
dan naskah yang dibangun dari isian formulir harus lolos pemeriksaan Python.
Jalankan: python3 tests/uji_web.py   (butuh node)"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.susun import cek_naskah

contoh = json.loads((ROOT / "examples" / "naskah.contoh.json").read_text(encoding="utf-8"))
dasar = lambda: json.loads(json.dumps(contoh))

kasus = [dasar()]
k = dasar(); del k["bagian"][1]["ucapan"]; kasus.append(k)                            # ucapan hilang
k = dasar(); k["bagian"][0]["tipe"] = "melayang"; kasus.append(k)                    # tipe tidak dikenal
k = dasar(); k["bagian"][2]["ucapan"] = ["hanya satu kalimat."]; kasus.append(k)     # poin tidak sama
k = dasar(); del k["bagian"][1]["sumber"]; kasus.append(k)                           # angka tanpa sumber
k = dasar(); k["bagian"][0]["ucapan"] = "Ini [perlu verifikasi] ya."; kasus.append(k)
k = dasar(); k["bagian"] = k["bagian"][1:]; kasus.append(k)                          # tidak diawali hook
k = dasar(); k["bagian"] = k["bagian"][:-1]; kasus.append(k)                         # tidak diakhiri penutup
k = dasar(); k["bagian"][0]["ucapan"] = "kata " * 200; kasus.append(k)               # terlalu panjang
k = dasar(); k["bagian"] = []; kasus.append(k)                                       # kosong
k = dasar(); del k["bagian"][1]["label"]; del k["bagian"][1]["nilai"]; kasus.append(k)   # field wajib hilang
k = dasar(); k["bagian"][0]["ucapan"] = "  "; kasus.append(k)                        # ucapan hanya spasi
k = dasar(); k["bagian"][3]["ucapan"] = "Kata *kunci dengan* tanda *bintang* aneh *"; kasus.append(k)

formulir = [{
    "style": "neon-3d", "judul": "Uji formulir", "voice": "Kore", "akun": "@akunkamu",
    "bagian": [
        {"tipe": "hook", "f": {"teks": "Baris *satu*\nBaris dua", "label": "Label uji", "ucapan": "Ini hook untuk menguji formulir web."}},
        {"tipe": "angka", "f": {"nilai": "1234,5", "desimal": "1", "akhiran": " unit", "label": "angka contoh", "sumber": "DATA CONTOH", "ucapan": "Angka ini hanya contoh."}},
        {"tipe": "poin", "f": {"judul": "Tiga poin", "poin": "Satu\nDua\nTiga", "ucapan": "Poin satu.\nPoin dua.\nPoin tiga."}},
        {"tipe": "bar", "f": {"judul": "Grafik", "satuan": " jt", "data": "A = 40\nB: 25,5\nC = 10", "sumber": "DATA CONTOH", "ucapan": "Grafik contoh."}},
        {"tipe": "gambar", "f": {"file": "aset/foto.jpg", "teks": "Gambar uji", "bingkai": "penuh", "mode": "auto", "ucapan": "Gambar uji."}},
        {"tipe": "label", "f": {"teks": "Label mandiri", "ucapan": "Label mandiri."}},
        {"tipe": "penutup", "f": {"teks": "Sampai *jumpa*", "ajakan": "Ikuti", "ucapan": "Sampai jumpa."}},
    ]},
    {"style": "kota-datar", "bagian": [{"tipe": "angka", "f": {"nilai": "abc", "ucapan": "x"}}, {"tipe": "bar", "f": {"data": "tanpa angka\nA = 1", "ucapan": "y"}}]},
]

p = subprocess.run(["node", str(ROOT / "tests" / "web_paritas.js")], input=json.dumps({"kasus": kasus, "formulir": formulir}),
                   capture_output=True, text=True, encoding="utf-8")
if p.returncode != 0:
    sys.exit("node gagal: " + p.stderr)
js = json.loads(p.stdout)
gagal = 0
for i, (n, hasil) in enumerate(zip(kasus, js["kasus"])):
    for nama, ketat in (("biasa", False), ("ketat", True)):
        g, pr = cek_naskah(n, ketat=ketat)
        sama = g == hasil[nama]["galat"] and pr == hasil[nama]["peringatan"]
        gagal += not sama
        print(("LOLOS " if sama else "GAGAL ") + f"paritas kasus {i + 1:2d} ({nama})")
        if not sama:
            print("   py:", g, pr, "\n   js:", hasil[nama]["galat"], hasil[nama]["peringatan"])

# naskah dari formulir lengkap harus lolos Python tanpa galat; formulir bermasalah harus ditandai di web
n0 = js["formulir"][0]
g, pr = cek_naskah(n0["naskah"], ketat=True)
ok = not g and not n0["ui"]["galat"]
gagal += not ok
print(("LOLOS " if ok else "GAGAL ") + "formulir lengkap -> naskah lolos aturan Python (ketat)", g or "", n0["ui"]["galat"] or "")
ok = n0["naskah"].get("gambar_user") == ["aset/foto.jpg"] and n0["naskah"]["bagian"][1]["nilai"] == 1234.5 \
    and n0["naskah"]["bagian"][3]["data"][1] == {"label": "B", "nilai": 25.5} and n0["naskah"]["bagian"][2]["ucapan"] == ["Poin satu.", "Poin dua.", "Poin tiga."]
gagal += not ok
print(("LOLOS " if ok else "GAGAL ") + "pemetaan isian: gambar_user otomatis, koma desimal, baris data bar, ucapan poin per baris")
n1 = js["formulir"][1]
ok = len(n1["ui"]["galat"]) == 2 and any("angka" in x for x in n1["ui"]["galat"]) and any("baris data tidak valid" in x for x in n1["ui"]["galat"])
gagal += not ok
print(("LOLOS " if ok else "GAGAL ") + "isian salah ditandai di web:", n1["ui"]["galat"])
print(f"\n{'semua lolos' if not gagal else str(gagal) + ' gagal'}")
sys.exit(1 if gagal else 0)

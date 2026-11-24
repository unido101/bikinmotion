"""Uji asap: setiap style harus bisa merender setiap jenis scene tanpa galat.
Jalankan dari akar repo: python3 tests/uji_dasar.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline import gaya
from pipeline.render import Renderer
from pipeline.validasi import validasi

TL = json.loads((Path(__file__).resolve().parent.parent / "examples" / "timeline.contoh.json").read_text())
gagal = 0
for d in gaya.daftar():
    g = gaya.muat(d["id"])
    masalah = g.cek()
    r = Renderer(TL, g, 15.0)
    for s in TL["scene"]:
        t = (s["mulai"] + s["selesai"]) / 2
        im = r.frame(t)
        ok = im.size == (g.W, g.H)
        if not ok or masalah:
            gagal += 1
        print(("LOLOS " if ok and not masalah else "GAGAL ") + f"{d['id']:16s} {s['tipe']:8s} t={t:.1f} {masalah or ''}")
# scene tambahan: label mandiri, gambar kartu dan penuh (gambar uji di tests/aset)
foto = str(Path(__file__).resolve().parent / "aset" / "foto_lebar.jpg")
EKSTRA = {"akun": "@uji", "scene": [
    {"tipe": "label", "mulai": 0, "selesai": 3, "teks": "Label mandiri uji"},
    {"tipe": "gambar", "mulai": 3, "selesai": 6, "file": foto, "teks": "Gambar kartu"},
    {"tipe": "gambar", "mulai": 6, "selesai": 9, "file": foto, "bingkai": "penuh", "teks": "Gambar penuh"},
], "subtitle": [{"mulai": 0, "selesai": 9, "teks": "Subtitle uji"}]}
for d in gaya.daftar():
    g = gaya.muat(d["id"])
    r = Renderer(EKSTRA, g, 9.0)
    for t, nama in ((1.5, "label"), (4.5, "gambar-kartu"), (7.5, "gambar-penuh")):
        ok = r.frame(t).size == (g.W, g.H)
        gagal += not ok
        print(("LOLOS " if ok else "GAGAL ") + f"{d['id']:16s} {nama:13s} t={t}")
kategori = {d["kategori"] for d in gaya.daftar()}
ok = {"2d-flat", "pixelart", "3d"} <= kategori
gagal += not ok
print(("LOLOS " if ok else "GAGAL ") + f"kategori style tersedia: {sorted(kategori)}")
galat, _ = validasi(json.loads(json.dumps(TL)), dasar=Path(__file__).resolve().parent.parent / "examples")
print("validasi contoh:", "LOLOS" if not galat else galat)
sys.exit(1 if gagal or galat else 0)

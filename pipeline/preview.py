"""Buat styles/<id>/preview.png untuk galeri pemilihan style.

Pemakaian: python -m pipeline.preview            (semua style)
           python -m pipeline.preview bold-neon  (satu style)
Isi preview memakai teks contoh, bukan fakta.
"""
import sys

from PIL import Image, ImageDraw

from . import gaya as gaya_mod
from .render import Renderer

CONTOH = {
    "scene": [
        {"tipe": "hook", "mulai": 0, "selesai": 10, "teks": ["Judul hook *contoh*", "baris kedua"], "label": "Label contoh!"},
        {"tipe": "angka", "mulai": 10, "selesai": 20, "nilai": 1234, "akhiran": "%", "label": "angka *contoh* untuk preview", "sumber": "DATA CONTOH"},
        {"tipe": "poin", "mulai": 20, "selesai": 30, "judul": "Tiga poin contoh", "poin": ["Poin pertama yang agak panjang", "Poin kedua", "Poin *ketiga*"]},
        {"tipe": "bar", "mulai": 30, "selesai": 40, "judul": "Grafik contoh", "satuan": "%", "data": [{"label": "Contoh A", "nilai": 60}, {"label": "Contoh B", "nilai": 35}, {"label": "Contoh C", "nilai": 15}], "sumber": "DATA CONTOH"},
        {"tipe": "penutup", "mulai": 40, "selesai": 50, "teks": ["Penutup *contoh*"], "ajakan": "Ikuti untuk lanjutannya"},
    ],
    "akun": "@akunkamu",
    "subtitle": [{"mulai": 0, "selesai": 50, "teks": "Subtitle contoh dengan kata kunci", "kata_kunci": ["kata", "kunci"]}],
}
WAKTU = [2.6, 12.0, 23.0, 34.0, 43.0]


def buat(id_style, lebar=300):
    g = gaya_mod.muat(id_style)
    r = Renderer(CONTOH, g, 50.0)
    kecil = []
    for t in WAKTU:
        im = r.frame(t)
        kecil.append(im.resize((lebar, int(g.H * lebar / g.W)), Image.LANCZOS))
    h = kecil[0].height
    lembar = Image.new("RGB", (lebar * len(kecil), h), (24, 24, 24))
    for i, im in enumerate(kecil):
        lembar.paste(im, (i * lebar, 0))
    jalur = g.folder / "preview.png"
    lembar.save(jalur)
    return jalur


if __name__ == "__main__":
    ids = sys.argv[1:] or [d["id"] for d in gaya_mod.daftar()]
    for i in ids:
        print("preview:", buat(i))

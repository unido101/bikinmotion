"""Bantu membuat style dari gambar referensi: ambil warna dominan.

Pemakaian: python -m pipeline.ekstrak_palet styles/<id>/reference/*.png
Keluaran: daftar warna dominan + usulan latar/teks/aksen. Hasilnya saran awal;
tipografi, ritme gerak, dan tata letak dinilai dari gambar referensi oleh manusia atau Claude.
"""
import colorsys
import sys
from collections import Counter

import numpy as np
from PIL import Image


def dominan(paths, jumlah=8):
    hitung = Counter()
    for p in paths:
        im = Image.open(p).convert("RGB")
        im.thumbnail((200, 200))
        q = im.quantize(colors=jumlah, method=Image.MEDIANCUT).convert("RGB")
        hitung.update(map(tuple, np.array(q).reshape(-1, 3).tolist()))
    total = sum(hitung.values())
    return [(c, n / total) for c, n in hitung.most_common(jumlah)]


def aksen_jenuh(paths, jumlah=5, min_sat=0.5, min_val=0.35):
    """Warna beraksen: hanya piksel jenuh dan cukup terang, dikelompokkan per kuantisasi 16 level.
    Menangkap elemen kecil (label merah, helm oranye) yang tertutup warna latar pada palet dominan."""
    hitung, total = Counter(), 0
    for p in paths:
        im = Image.open(p).convert("RGB")
        im.thumbnail((240, 240))
        arr = np.array(im).reshape(-1, 3)
        mx, mn = arr.max(axis=1).astype(float), arr.min(axis=1).astype(float)
        sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
        pilih = arr[(sat >= min_sat) & (mx / 255 >= min_val)]
        total += len(arr)
        if len(pilih):
            q = (pilih // 16) * 16 + 8
            hitung.update(map(tuple, q.tolist()))
    return [(c, n / max(total, 1)) for c, n in hitung.most_common(jumlah)]


def hex_(c):
    return "#{:02X}{:02X}{:02X}".format(*c)


def usulan(warna):
    def sat(c):
        return colorsys.rgb_to_hsv(*(v / 255 for v in c))[1]

    def terang(c):
        return sum(c) / 3
    daftar = [c for c, _ in warna]
    latar = max(warna, key=lambda x: x[1])[0]
    teks = max(daftar, key=lambda c: abs(terang(c) - terang(latar)))
    aksen = max((c for c in daftar if c not in (latar, teks)), key=lambda c: sat(c) * (0.4 + abs(terang(c) - terang(latar)) / 255), default=teks)
    return {"latar": hex_(latar), "teks": hex_(teks), "aksen": hex_(aksen)}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    w = dominan(sys.argv[1:])
    print("Warna dominan:")
    for c, p in w:
        print(f"  {hex_(c)}  {p * 100:5.1f}%")
    print("Warna beraksen (piksel jenuh):")
    for c, p in aksen_jenuh(sys.argv[1:]):
        print(f"  {hex_(c)}  {p * 100:5.2f}% dari seluruh gambar")
    print("usulan awal:", usulan(w), "(saran kasar; periksa visual dan sesuaikan)")

"""Validasi timeline sebelum render. Return (galat, peringatan)."""
import os
from pathlib import Path

from . import gaya as gaya_mod

WAJIB = {
    "hook": ["teks"], "angka": ["nilai", "label"], "poin": ["poin"],
    "gambar": ["file"], "bar": ["data"], "penutup": ["teks"], "label": ["teks"],
}
PERLU_SUMBER = {"angka", "bar"}


def validasi(tl, dasar=".", ketat=False):
    galat, peringatan = [], []
    dasar = Path(dasar)

    try:
        g = gaya_mod.muat(tl.get("style", "bersih-edukasi"))
        galat += g.cek()
    except FileNotFoundError as e:
        galat.append(str(e))

    scene = tl.get("scene") or []
    if not scene:
        galat.append("timeline tidak punya scene")
    dipakai = set()
    for i, s in enumerate(scene):
        nama = f"scene {i + 1} ({s.get('tipe', '?')})"
        if s.get("tipe") not in WAJIB:
            galat.append(f"{nama}: tipe tidak dikenal; pilihan: {', '.join(WAJIB)}")
            continue
        for k in WAJIB[s["tipe"]]:
            if k not in s:
                galat.append(f"{nama}: field '{k}' wajib ada")
        if not (isinstance(s.get("mulai"), (int, float)) and isinstance(s.get("selesai"), (int, float))):
            galat.append(f"{nama}: 'mulai' dan 'selesai' harus angka (detik)")
        elif s["selesai"] <= s["mulai"]:
            galat.append(f"{nama}: 'selesai' harus lebih besar dari 'mulai'")
        if s["tipe"] == "gambar" and "file" in s:
            p = Path(s["file"]) if os.path.isabs(s["file"]) else dasar / s["file"]
            s["file"] = str(p)
            dipakai.add(os.path.normpath(str(p)))
            if not p.exists():
                galat.append(f"{nama}: file gambar tidak ada: {p}")
        if s["tipe"] == "bar" and not (1 <= len(s.get("data", [])) <= 6):
            galat.append(f"{nama}: bar harus berisi 1 sampai 6 data")
        if s["tipe"] in PERLU_SUMBER and not s.get("sumber"):
            (galat if ketat else peringatan).append(
                f"{nama}: angka tanpa 'sumber'. Pastikan datanya dari user atau sumber yang terverifikasi")

    # gambar dari user wajib dipakai
    for f in tl.get("gambar_user", []):
        p = Path(f) if os.path.isabs(f) else dasar / f
        if os.path.normpath(str(p)) not in dipakai:
            galat.append(f"gambar dari user tidak dipakai di scene mana pun: {f}")

    # celah layar kosong
    ada = sorted((s["mulai"], s["selesai"]) for s in scene
                 if isinstance(s.get("mulai"), (int, float)) and isinstance(s.get("selesai"), (int, float)))
    akhir = 0.0
    for m, e in ada:
        if m - akhir > 0.6:
            peringatan.append(f"layar kosong {akhir:.1f}s sampai {m:.1f}s (tidak ada scene)")
        akhir = max(akhir, e)

    for j, sub in enumerate(tl.get("subtitle", [])):
        if not (sub.get("selesai", 0) > sub.get("mulai", 1) and sub.get("teks")):
            galat.append(f"subtitle {j + 1}: waktu atau teks tidak valid")
    return galat, peringatan

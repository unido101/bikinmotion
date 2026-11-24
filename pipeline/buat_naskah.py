"""CLI: topik (+ fakta dari user) -> naskah.json lewat Gemini. Naskah harus kamu setujui sebelum render.

  python -m pipeline.buat_naskah --topik "Kenapa laut asin" --fakta fakta.txt --durasi 40 --out naskah.json

fakta.txt: satu fakta per baris (satu-satunya sumber fakta yang boleh dipakai model).
"""
import argparse
import json
import sys
from pathlib import Path

from .naskah_gemini import NaskahGalat, buat_naskah
from .susun import teks_vo


def main(argv=None):
    from .buat_video import _utf8
    _utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("--topik", required=True)
    ap.add_argument("--fakta", help="berkas teks, satu fakta per baris")
    ap.add_argument("--durasi", type=int, default=40, help="target detik (perkiraan)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    fakta = [x.strip() for x in Path(a.fakta).read_text(encoding="utf-8").splitlines() if x.strip()] if a.fakta else []
    try:
        n, peringatan = buat_naskah(a.topik, fakta, a.durasi)
    except NaskahGalat as e:
        print("GAGAL:", e)
        return 1
    Path(a.out).write_text(json.dumps(n, ensure_ascii=False, indent=2), encoding="utf-8")
    _, kata, _ = teks_vo(n)
    print(f"naskah tersimpan: {a.out} ({len(kata)} kata, perkiraan {len(kata) / 2.7:.0f} detik)")
    for p in peringatan:
        print("PERINGATAN:", p)
    if n.get("perlu_dicari"):
        print("FAKTA YANG MASIH DIBUTUHKAN (belum ada di fakta.txt):")
        for x in n["perlu_dicari"]:
            print("  -", x)
    print("Baca naskahnya dan setujui sebelum render.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

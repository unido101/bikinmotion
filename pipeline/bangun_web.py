"""Menyiapkan folder web/ untuk Vercel: daftar style (styles.json), pratinjau WebP, dan font.

  python -m pipeline.bangun_web

Jalankan ulang setiap kali menambah atau mengubah style (setelah `python -m pipeline.preview`).
"""
import json
import shutil
import sys

from PIL import Image

from . import gaya

WEB = gaya.ROOT / "web"
FONT_WEB = ["ArchivoBlack-Regular.ttf", "Poppins-Regular.ttf", "Poppins-Medium.ttf", "Poppins-Bold.ttf"]


def main():
    (WEB / "previews").mkdir(parents=True, exist_ok=True)
    (WEB / "fonts").mkdir(parents=True, exist_ok=True)
    urut = {"2d-flat": 0, "pixelart": 1, "3d": 2}
    daftar = []
    for d in gaya.daftar():
        g = gaya.muat(d["id"])
        if not d["preview"]:
            print(f"lewati {d['id']}: belum ada preview.png (jalankan: python -m pipeline.preview)", file=sys.stderr)
            continue
        im = Image.open(gaya.ROOT / d["preview"]).convert("RGB")
        im.save(WEB / "previews" / f"{d['id']}.webp", "WEBP", quality=82, method=6)
        w = g.data["warna"]
        daftar.append({"id": d["id"], "nama": d["nama"], "kategori": d["kategori"], "deskripsi": d["deskripsi"],
                       "preview": f"previews/{d['id']}.webp", "lebar": im.width, "tinggi": im.height,
                       "warna": [w["latar"], w["aksen"], w["aksen2"], w["teks"]]})
    daftar.sort(key=lambda x: (urut.get(x["kategori"], 9), x["nama"]))
    (WEB / "styles.json").write_text(json.dumps(daftar, ensure_ascii=False, indent=1), encoding="utf-8")
    for f in FONT_WEB:
        shutil.copy(gaya.FONT_DIR / f, WEB / "fonts" / f)
    print(f"web/: {len(daftar)} style, pratinjau WebP, {len(FONT_WEB)} font")


if __name__ == "__main__":
    main()

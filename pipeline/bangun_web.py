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


CSP = ("default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data: https://*.supabase.co; font-src 'self'; connect-src 'self' https://*.supabase.co; "
       "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'")


def konfigurasi_vercel(akar):
    """Isi vercel.json. `akar=True` untuk berkas di akar repo (dipakai bila Root Directory belum diisi `web`).
    framework null = preset Other: menimpa preset Python yang tersimpan di proyek."""
    c = {"$schema": "https://openapi.vercel.sh/vercel.json", "framework": None, "buildCommand": None,
         "installCommand": None}
    if akar:
        c["outputDirectory"] = "web"
    c["cleanUrls"] = True
    c["headers"] = [
        {"source": "/(.*)", "headers": [
            {"key": "Content-Security-Policy", "value": CSP},
            {"key": "X-Content-Type-Options", "value": "nosniff"},
            {"key": "X-Frame-Options", "value": "DENY"},
            {"key": "Referrer-Policy", "value": "strict-origin-when-cross-origin"}]},
        {"source": "/fonts/(.*)", "headers": [{"key": "Cache-Control", "value": "public, max-age=31536000, immutable"}]},
        {"source": "/previews/(.*)", "headers": [{"key": "Cache-Control", "value": "public, max-age=86400"}]},
    ]
    return c


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
    for jalur, akar in ((WEB / "vercel.json", False), (gaya.ROOT / "vercel.json", True)):
        jalur.write_text(json.dumps(konfigurasi_vercel(akar), indent=2) + "\n", encoding="utf-8")
    print(f"web/: {len(daftar)} style, pratinjau WebP, {len(FONT_WEB)} font")


if __name__ == "__main__":
    main()

"""Pengecekan visual: lembar kontak dari frame penting + deteksi frame hitam."""
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw


def ambil_frame(mp4, detik, keluar):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{detik:.3f}", "-i", str(mp4),
                    "-frames:v", "1", str(keluar)], check=True)
    return Image.open(keluar).convert("RGB")


def waktu_penting(tl, durasi):
    """Awal frame, tengah tiap scene, dan frame terakhir."""
    ts = [0.05]
    for s in sorted(tl["scene"], key=lambda x: x["mulai"]):
        if s["mulai"] < durasi:
            ts.append(min(s["selesai"], durasi) - (min(s["selesai"], durasi) - s["mulai"]) * 0.45)
    ts.append(max(0.05, durasi - 0.1))
    return ts


def lembar_kontak(mp4, waktu, keluar_png, kolom=6, lebar=240, tmp="tmp_qc"):
    Path(tmp).mkdir(exist_ok=True)
    kecil = []
    for i, t in enumerate(waktu):
        im = ambil_frame(mp4, t, Path(tmp) / f"f{i:02d}.png")
        h = int(im.height * lebar / im.width)
        im = im.resize((lebar, h), Image.LANCZOS)
        ImageDraw.Draw(im).text((8, 8), f"{t:.1f}s", fill=(255, 255, 0))
        kecil.append(im)
    baris = (len(kecil) + kolom - 1) // kolom
    h = kecil[0].height
    lembar = Image.new("RGB", (kolom * lebar, baris * h), (30, 30, 30))
    for i, im in enumerate(kecil):
        lembar.paste(im, ((i % kolom) * lebar, (i // kolom) * h))
    lembar.save(keluar_png)
    return keluar_png


def frame_hitam(mp4, ambang=0.98):
    """Daftar interval frame hitam penuh (kecuali awal 0 s) lewat ffmpeg blackdetect."""
    p = subprocess.run(["ffmpeg", "-i", str(mp4), "-vf", f"blackdetect=d=0.1:pix_th=0.04:pic_th={ambang}",
                        "-an", "-f", "null", "-"], capture_output=True, text=True)
    return [ln.split("black_start:")[1].split()[0] for ln in p.stderr.splitlines() if "black_start" in ln]


if __name__ == "__main__":
    print("pemakaian: dipanggil dari buat_video.py", file=sys.stderr)

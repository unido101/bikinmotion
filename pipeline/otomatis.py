"""Satu perintah: naskah.json -> VO -> timestamps -> timeline -> MP4 yang sudah dicek.

Contoh:
  python -m pipeline.otomatis --naskah naskah.json --out hasil/video.mp4                  # TTS Gemini + Whisper
  python -m pipeline.otomatis --naskah naskah.json --audio vo.wav --out hasil/video.mp4   # VO sendiri
  python -m pipeline.otomatis --naskah examples/naskah.contoh.json --tts tiruan --out ... # uji tanpa jaringan
"""
import argparse
import json
import os
import sys
from pathlib import Path

from . import buat_video, jalankan
from .susun import cek_naskah, teks_vo


def _mutlak(n, dasar):
    """Ubah path gambar relatif (terhadap folder naskah) menjadi mutlak."""
    n["gambar_user"] = [str(Path(dasar) / f) if not os.path.isabs(f) else f for f in n.get("gambar_user", [])]
    for b in n["bagian"]:
        if b.get("tipe") == "gambar" and "file" in b and not os.path.isabs(b["file"]):
            b["file"] = str(Path(dasar) / b["file"])
    return n


def main(argv=None):
    buat_video._utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("--naskah", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--audio", help="VO sendiri (melewati TTS)")
    ap.add_argument("--tts", choices=["gemini", "tiruan"], default="gemini")
    ap.add_argument("--selaras", choices=["auto", "whisper", "diam"], default="auto")
    ap.add_argument("--whisper-ukuran", default="small")
    ap.add_argument("--musik")
    ap.add_argument("--ekor", type=float, default=0.5)
    ap.add_argument("--ketat", action="store_true")
    a = ap.parse_args(argv)

    naskah_path = Path(a.naskah)
    n = _mutlak(json.loads(naskah_path.read_text(encoding="utf-8")), naskah_path.parent)
    out = Path(a.out)
    kerja = out.parent / (out.stem + "_kerja")
    kerja.mkdir(parents=True, exist_ok=True)

    galat, peringatan = cek_naskah(n, ketat=a.ketat)
    for p in peringatan:
        print("  PERINGATAN:", p)
    if galat:
        for e in galat:
            print("  GALAT:", e)
        return 2
    _, kata, _ = teks_vo(n)
    print(f"  {len(kata)} kata VO (perkiraan {len(kata) / 2.7:.0f} detik)")

    terakhir = {"t": None}

    def lapor(tahap, persen):
        if tahap != terakhir["t"]:
            terakhir["t"] = tahap
            print(f"[{persen:3d}%] {tahap}")

    try:
        hasil = jalankan.buat(
            n, dasar=naskah_path.parent, kerja=kerja, keluar=out,
            tts="tiruan" if a.tts == "tiruan" else "gemini",
            kunci_gemini=os.environ.get("GEMINI_API_KEY"), audio=a.audio,
            selaras_metode=a.selaras, whisper_ukuran=a.whisper_ukuran, musik=a.musik, ekor=a.ekor,
            ketat=a.ketat, lapor=lapor)
    except jalankan.GalatNaskah as e:
        print("GALAT NASKAH:", e)
        return 2
    except (jalankan.GalatProses, RuntimeError) as e:
        print("GAGAL:", e)
        return 3
    for p in hasil["peringatan"]:
        print("  PERINGATAN:", p)
    print(f"SELESAI: {out}\n  lembar kontak: {hasil['kontak']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

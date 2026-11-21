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

from . import buat_video, selaras
from .susun import cek_naskah, susun, teks_vo


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

    print("1/5 periksa naskah")
    galat, peringatan = cek_naskah(n, ketat=a.ketat)
    for p in peringatan:
        print("  PERINGATAN:", p)
    if galat:
        for e in galat:
            print("  GALAT:", e)
        return 2
    vo_teks, kata, _ = teks_vo(n)
    kata_str = [k for k, _ in kata]
    print(f"  {len(kata_str)} kata VO (perkiraan {len(kata_str) / 2.7:.0f} detik)")

    print("2/5 suara (VO)")
    if a.audio:
        audio = Path(a.audio)
        print(f"  memakai VO dari user: {audio}")
        exact = None
    elif a.tts == "tiruan":
        from .tts_tiruan import sintesis_tiruan
        audio = kerja / "vo.wav"
        exact = sintesis_tiruan(kata_str, audio)
        print("  TTS TIRUAN (nada, hanya untuk uji)")
    else:
        from .tts_gemini import sintesis
        audio = kerja / "vo.wav"
        sintesis(vo_teks, audio, voice=n.get("voice", "Kore"))
        print(f"  VO dibuat dengan Gemini TTS: {audio}")
        exact = None

    print("3/5 timestamps kata")
    if exact is not None:
        kata_waktu, metode, akurat = [dict(x, cocok=True) for x in exact], "tepat (tiruan)", True
    else:
        kata_waktu, metode, akurat = selaras.hitung(kata_str, audio, a.selaras, a.whisper_ukuran)
    cocok = sum(1 for k in kata_waktu if k.get("cocok"))
    print(f"  metode: {metode}; kata cocok langsung {cocok}/{len(kata_waktu)}")
    if not akurat:
        print("  PERINGATAN: sinkron hanya perkiraan dari jeda audio. Cek lembar kontak; pasang faster-whisper untuk hasil akurat")
    (kerja / "kata.json").write_text(json.dumps(kata_waktu, ensure_ascii=False, indent=1), encoding="utf-8")

    print("4/5 susun timeline")
    vo_dur = selaras.durasi(audio)
    tl, pr = susun(n, kata_waktu, round(vo_dur + a.ekor, 3))
    for p in pr:
        print("  PERINGATAN:", p)
    tl_path = kerja / "timeline.json"
    tl_path.write_text(json.dumps(tl, ensure_ascii=False, indent=1), encoding="utf-8")

    print("5/5 render dan cek")
    args = ["--timeline", str(tl_path), "--audio", str(audio), "--out", str(out), "--ekor", str(a.ekor)]
    if a.musik:
        args += ["--musik", a.musik]
    if a.ketat:
        args += ["--ketat"]
    return buat_video.main(args)


if __name__ == "__main__":
    sys.exit(main())

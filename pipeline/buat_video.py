"""CLI: timeline JSON (+ audio VO) -> MP4 30 fps yang sudah dicek.

Contoh:
  python -m pipeline.buat_video --timeline examples/timeline.contoh.json --audio vo.wav --out hasil/video.mp4
Tanpa --audio: render DRAFT bisu dengan durasi dari timeline (bukan hasil final).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import gaya as gaya_mod
from .qc import frame_hitam, lembar_kontak, waktu_penting
from .render import render_video
from .validasi import validasi

ROOT = Path(__file__).resolve().parent.parent


def durasi_media(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeline", required=True)
    ap.add_argument("--audio", help="berkas VO utuh; durasi video mengikuti VO")
    ap.add_argument("--musik")
    ap.add_argument("--style", help="menimpa style di timeline")
    ap.add_argument("--out", required=True)
    ap.add_argument("--ekor", type=float, default=0.5)
    ap.add_argument("--ketat", action="store_true", help="angka tanpa sumber dianggap galat")
    a = ap.parse_args(argv)

    tl_path = Path(a.timeline)
    tl = json.loads(tl_path.read_text(encoding="utf-8"))
    if a.style:
        tl["style"] = a.style
    dasar = tl_path.parent

    print("1/5 validasi timeline")
    galat, peringatan = validasi(tl, dasar=dasar, ketat=a.ketat)
    for p in peringatan:
        print("  PERINGATAN:", p)
    if galat:
        for e in galat:
            print("  GALAT:", e)
        return 2

    g = gaya_mod.muat(tl["style"])
    if a.audio:
        vo = durasi_media(a.audio)
        durasi = round(vo + a.ekor, 3)
        print(f"  durasi VO {vo:.2f}s + ekor {a.ekor}s = {durasi}s")
    else:
        durasi = max(s["selesai"] for s in tl["scene"])
        print(f"  TANPA AUDIO: draft bisu, durasi {durasi}s dari timeline (bukan final)")

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    bisu = out.with_suffix(".bisu.mp4")
    print(f"2/5 render {round(durasi * g.fps)} frame ({g.W}x{g.H}, {g.fps} fps, style {g.id})")
    render_video(tl, g, durasi, bisu)

    print("3/5 rakit audio dan video")
    if a.audio:
        cmd = ["bash", str(ROOT / "scripts" / "rakit_mp4.sh"), str(bisu), a.audio, str(out)]
        if a.musik:
            cmd += [a.musik, str(a.ekor)]
        else:
            cmd += ["", str(a.ekor)]
        r = subprocess.run(cmd)
        if r.returncode != 0:
            print("  GAGAL: pengecekan teknis tidak lolos (lihat di atas)")
            return 3
        bisu.unlink(missing_ok=True)
    else:
        shutil.move(bisu, out)

    print("4/5 cek frame hitam")
    hitam = [t for t in frame_hitam(out) if float(t) > 0.2]
    print("  tidak ada frame hitam" if not hitam else f"  PERINGATAN: frame hitam mulai detik {hitam}")

    print("5/5 lembar kontak untuk cek visual")
    kontak = lembar_kontak(out, waktu_penting(tl, durasi), out.with_suffix(".kontak.png"), tmp=str(out.parent / "tmp_qc"))
    shutil.rmtree(out.parent / "tmp_qc", ignore_errors=True)
    print(f"SELESAI: {out}\n  lembar kontak: {kontak}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

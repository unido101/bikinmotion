"""Satu fungsi untuk seluruh alur naskah -> MP4. Dipakai CLI (otomatis.py) dan worker server.

Tidak membaca variabel lingkungan dan tidak mencetak apa pun: kunci API dan kemajuan masuk lewat parameter.
"""
import json
from pathlib import Path

from . import gaya as gaya_mod
from . import selaras
from .qc import frame_hitam, lembar_kontak, waktu_penting
from .rakit import rakit
from .render import render_video
from .susun import cek_naskah, susun, teks_vo
from .validasi import validasi


class GalatNaskah(Exception):
    """Masalah yang bisa diperbaiki pengguna (pesan dalam bahasa Indonesia)."""


class GalatProses(Exception):
    """Kegagalan teknis saat memproses (rakit, render)."""


def buat(naskah, dasar, kerja, keluar, *, tts="gemini", kunci_gemini=None, audio=None, selaras_metode="auto",
         whisper_ukuran="small", musik=None, ekor=0.5, ketat=False, lapor=None, opsi_tts=None, kontak=True):
    """Return dict: durasi, keluar, kontak, metode_selaras, akurat, peringatan, jumlah_kata.

    lapor(tahap: str, persen: int) dipanggil di tiap tahap; boleh melempar exception untuk menghentikan proses.
    tts: "gemini" (butuh kunci_gemini), "tiruan" (nada, hanya uji), atau berikan `audio` (berkas VO milik user).
    """
    lapor = lapor or (lambda tahap, persen: None)
    dasar, kerja, keluar = Path(dasar), Path(kerja), Path(keluar)
    kerja.mkdir(parents=True, exist_ok=True)
    keluar.parent.mkdir(parents=True, exist_ok=True)
    peringatan = []

    lapor("Memeriksa naskah", 3)
    galat, pr = cek_naskah(naskah, ketat=ketat)
    peringatan += pr
    if galat:
        raise GalatNaskah("; ".join(galat))
    try:
        g = gaya_mod.muat(naskah.get("style", "bersih-edukasi"))
    except (FileNotFoundError, ValueError):
        raise GalatNaskah(f"Style tidak dikenal: {naskah.get('style')}")
    vo_teks, kata, _ = teks_vo(naskah)
    kata_str = [k for k, _ in kata]

    lapor("Membuat suara", 8)
    exact = None
    if audio:
        audio = Path(audio)
    elif tts == "tiruan":
        from .tts_tiruan import sintesis_tiruan
        audio = kerja / "vo.wav"
        exact = sintesis_tiruan(kata_str, audio)
    else:
        from .tts_gemini import sintesis
        audio = kerja / "vo.wav"
        sintesis(vo_teks, audio, voice=naskah.get("voice") or "Kore", api_key=kunci_gemini, **(opsi_tts or {}))

    lapor("Menyelaraskan waktu", 30)
    if exact is not None:
        kata_waktu, metode, akurat = [dict(x, cocok=True) for x in exact], "tepat (tiruan)", True
    else:
        kata_waktu, metode, akurat = selaras.hitung(kata_str, audio, selaras_metode, whisper_ukuran)
    if not akurat:
        peringatan.append("Sinkron waktu hanya perkiraan dari jeda audio.")
    (kerja / "kata.json").write_text(json.dumps(kata_waktu, ensure_ascii=False, indent=1), encoding="utf-8")

    lapor("Menyusun timeline", 38)
    vo_dur = selaras.durasi(audio)
    tl, pr = susun(naskah, kata_waktu, round(vo_dur + ekor, 3))
    peringatan += pr
    galat2, pr2 = validasi(tl, dasar=dasar, ketat=ketat)
    peringatan += pr2
    if galat2:
        raise GalatNaskah("; ".join(galat2))
    (kerja / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False, indent=1), encoding="utf-8")

    durasi = round(vo_dur + ekor, 3)
    lapor("Merender video", 40)
    bisu = kerja / "bisu.mp4"
    render_video(tl, g, durasi, bisu, tampil_progres=False,
                 kemajuan=lambda i, n: lapor("Merender video", 40 + int(46 * i / max(1, n))))

    lapor("Merakit audio dan video", 88)
    ok, laporan = rakit(bisu, audio, keluar, musik=musik, ekor=ekor)
    if not ok:
        raise GalatProses("Pengecekan teknis gagal: " + "; ".join(f"{n} ({d})" for n, l, d in laporan if not l))
    bisu.unlink(missing_ok=True)

    hasil_kontak = None
    if kontak:
        lapor("Membuat lembar kontak", 94)
        hitam = [t for t in frame_hitam(keluar) if float(t) > 0.2]
        if hitam:
            peringatan.append(f"Ada frame hitam mulai detik {hitam}.")
        hasil_kontak = lembar_kontak(keluar, waktu_penting(tl, durasi), keluar.with_suffix(".kontak.png"),
                                     tmp=str(kerja / "tmp_qc"))
    return {"durasi": durasi, "keluar": keluar, "kontak": hasil_kontak, "metode_selaras": metode, "akurat": akurat,
            "peringatan": peringatan, "jumlah_kata": len(kata_str), "timeline": tl}

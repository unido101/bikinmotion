"""Memproses satu job: validasi ketat -> suara (kunci milik pengguna) -> render -> unggah hasil.

Aturan keamanan (worker memakai kunci layanan yang menembus RLS, jadi semua yang berasal dari pengguna dicurigai):
- Gambar hanya boleh berupa objek storage milik pemilik job (`unggahan:<user_id>/<nama>`); jalur lokal ditolak.
- Semua isi naskah dibatasi (jumlah, panjang, angka); gambar divalidasi sebagai PNG/JPEG/WEBP dan dibatasi piksel.
- Kunci API tidak pernah dicatat di log, pesan galat, atau tabel job.
"""
import math
import re
import shutil
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from pipeline import gaya as gaya_mod
from pipeline import jalankan
from pipeline.tts_gemini import TTSGalat
from pipeline.validasi import WAJIB

from .rest import BerkasTerlaluBesar, RestGalat

BATAS = {
    "naskah_karakter": 200_000, "bagian": 40, "kata_vo": 450, "gambar": 12,
    "gambar_byte": 8 * 1024 * 1024, "gambar_piksel": 40_000_000, "gambar_sisi": 9000,
    "string": 500, "string_ucapan": 3000, "daftar": 12, "waktu_detik": 20 * 60,
}
POLA_GAMBAR = re.compile(r"^unggahan:([0-9a-fA-F-]{36})/([A-Za-z0-9][A-Za-z0-9._-]{0,99})$")
FORMAT_OK = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp"}


class GalatPengguna(Exception):
    """Pesan yang aman dan berguna untuk ditampilkan kepada pemilik job."""


def scrub(teks, *rahasia):
    teks = str(teks)
    for r in rahasia:
        if r and len(r) >= 8:
            teks = teks.replace(r, "***")
    return teks


def sekarang():
    return datetime.now(timezone.utc).isoformat()


def _bersihkan(nilai, kedalaman=0, kunci=None):
    """Batasi bentuk dan ukuran isi naskah. Teks VO (`ucapan`) boleh lebih panjang dari teks tampilan;
    daftar `bagian` punya batas sendiri (diperiksa di siapkan_naskah), bukan batas daftar umum."""
    if kedalaman > 5:
        raise GalatPengguna("Struktur naskah terlalu dalam.")
    if isinstance(nilai, str):
        maks = BATAS["string_ucapan"] if kunci == "ucapan" else BATAS["string"]
        if len(nilai) > maks:
            raise GalatPengguna(f"Ada teks lebih dari {maks} karakter; pecah menjadi beberapa bagian.")
        return nilai
    if isinstance(nilai, bool) or nilai is None:
        return nilai
    if isinstance(nilai, (int, float)):
        if not math.isfinite(nilai) or abs(nilai) > 1e15:
            raise GalatPengguna("Ada angka yang tidak wajar di naskah.")
        return nilai
    if isinstance(nilai, list):
        batas = BATAS["bagian"] if kunci == "bagian" else BATAS["daftar"]
        if len(nilai) > batas:
            raise GalatPengguna(f"Maksimal {batas} bagian per video." if kunci == "bagian" else f"Ada daftar dengan lebih dari {batas} item.")
        return [_bersihkan(x, kedalaman + 1, kunci if kunci == "ucapan" else None) for x in nilai]
    if isinstance(nilai, dict):
        if len(nilai) > 30:
            raise GalatPengguna("Ada objek dengan terlalu banyak isian.")
        return {str(k)[:40]: _bersihkan(v, kedalaman + 1, str(k)) for k, v in nilai.items()}
    raise GalatPengguna("Ada isian naskah dengan jenis yang tidak didukung.")


def siapkan_naskah(job, kerja, rest, log=print):
    """Validasi, bersihkan, dan unduh gambar. Return naskah siap pakai (path gambar relatif ke `kerja`)."""
    uid = str(job["user_id"]).lower()
    naskah = job.get("naskah")
    if not isinstance(naskah, dict):
        raise GalatPengguna("Naskah tidak valid.")
    if len(str(naskah)) > BATAS["naskah_karakter"]:
        raise GalatPengguna("Naskah terlalu besar.")
    naskah = _bersihkan(naskah)
    for terlarang in ("musik", "audio", "gambar_user"):
        naskah.pop(terlarang, None)

    bagian = naskah.get("bagian")
    if not isinstance(bagian, list) or not bagian:
        raise GalatPengguna("Naskah tidak punya bagian.")
    if len(bagian) > BATAS["bagian"]:
        raise GalatPengguna(f"Maksimal {BATAS['bagian']} bagian per video.")
    for i, b in enumerate(bagian):
        if not isinstance(b, dict) or b.get("tipe") not in WAJIB:
            raise GalatPengguna(f"Bagian {i + 1}: jenis bagian tidak dikenal.")
        if "desimal" in b:
            try:
                b["desimal"] = max(0, min(6, int(b["desimal"])))
            except (TypeError, ValueError):
                b["desimal"] = 0
        if b["tipe"] == "bar" and isinstance(b.get("data"), list):
            if not all(isinstance(d, dict) and isinstance(d.get("nilai"), (int, float)) for d in b["data"]):
                raise GalatPengguna(f"Bagian {i + 1}: data grafik harus berisi label dan angka.")

    ids = {d["id"] for d in gaya_mod.daftar()}
    if naskah.get("style") not in ids:
        raise GalatPengguna(f"Style tidak dikenal: {naskah.get('style')}")
    voice = naskah.get("voice")
    naskah["voice"] = voice if isinstance(voice, str) and re.fullmatch(r"[A-Za-z]{2,24}", voice) else "Kore"
    akun = naskah.get("akun")
    if akun is not None:
        akun = re.sub(r"[\x00-\x1f\x7f]", "", str(akun))[:40]
        naskah["akun"] = akun

    from pipeline.susun import teks_vo
    try:
        _, kata, _ = teks_vo(naskah)
    except (KeyError, TypeError, AttributeError):
        raise GalatPengguna("Ada bagian tanpa kalimat VO (ucapan).")
    if len(kata) > BATAS["kata_vo"]:
        raise GalatPengguna(f"Naskah {len(kata)} kata; maksimal {BATAS['kata_vo']} kata (sekitar 2,5 menit).")

    # gambar: hanya objek storage milik pemilik job
    peta, urut = {}, []
    for i, b in enumerate(bagian):
        if b["tipe"] != "gambar":
            continue
        m = POLA_GAMBAR.match(str(b.get("file", "")))
        if not m or m.group(1).lower() != uid or ".." in m.group(2):
            raise GalatPengguna(f"Bagian {i + 1}: gambar tidak diizinkan. Unggah gambar lewat halaman studio.")
        if b["file"] not in peta:
            if len(peta) >= BATAS["gambar"]:
                raise GalatPengguna(f"Maksimal {BATAS['gambar']} gambar per video.")
            peta[b["file"]] = None
            urut.append((b["file"], m.group(2)))
    (kerja / "aset").mkdir(parents=True, exist_ok=True)
    for n, (ref, nama) in enumerate(urut, 1):
        sementara = kerja / "aset" / f"unduh-{n}"
        try:
            rest.unduh("unggahan", f"{uid}/{nama}", sementara, BATAS["gambar_byte"])
        except BerkasTerlaluBesar:
            raise GalatPengguna(f"Gambar {nama} lebih dari 8 MB.")
        except RestGalat as e:
            if e.status in (400, 404):
                raise GalatPengguna(f"Gambar {nama} tidak ditemukan. Unggah ulang gambarnya.")
            raise
        peta[ref] = _periksa_gambar(sementara, kerja / "aset", n, nama)
    for b in bagian:
        if b["tipe"] == "gambar":
            b["file"] = peta[b["file"]]
    naskah["gambar_user"] = sorted(set(peta.values()))
    return naskah


def _periksa_gambar(sementara, folder, n, nama):
    Image.MAX_IMAGE_PIXELS = BATAS["gambar_piksel"]
    try:
        with Image.open(sementara) as im:
            fmt, ukuran = im.format, im.size
            im.verify()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise GalatPengguna(f"Gambar {nama} terlalu besar (jumlah pikselnya berlebihan).")
    except Exception:
        raise GalatPengguna(f"{nama} bukan gambar yang valid.")
    if fmt not in FORMAT_OK:
        raise GalatPengguna(f"{nama}: format harus PNG, JPEG, atau WEBP.")
    if max(ukuran) > BATAS["gambar_sisi"] or ukuran[0] * ukuran[1] > BATAS["gambar_piksel"]:
        raise GalatPengguna(f"Gambar {nama} terlalu besar (maksimal {BATAS['gambar_sisi']} piksel per sisi).")
    tujuan = folder / f"gambar-{n}.{FORMAT_OK[fmt]}"
    sementara.rename(tujuan)
    return f"aset/{tujuan.name}"


def proses_job(rest, job, id_worker="worker", tts="gemini", opsi_tts=None, log=print):
    """Jalankan satu job sampai selesai atau gagal. Tidak melempar exception ke pemanggil."""
    jid, uid = job["id"], str(job["user_id"]).lower()
    kerja = Path(tempfile.mkdtemp(prefix=f"job-{str(jid)[:8]}-"))
    mulai, terakhir, kunci = time.time(), [0.0], None

    def lapor(tahap, persen):
        if time.time() - mulai > BATAS["waktu_detik"]:
            raise GalatPengguna("Pemrosesan melewati batas waktu 20 menit. Coba naskah yang lebih pendek.")
        t = time.time()
        if t - terakhir[0] >= 2.0 or persen >= 95:
            terakhir[0] = t
            rest.patch_job(jid, {"progres": int(persen), "tahap": tahap, "diperbarui": sekarang()})

    def gagal(pesan):
        try:
            rest.patch_job(jid, {"status": "gagal", "tahap": None, "pesan": scrub(pesan, kunci)[:300], "selesai": sekarang(),
                                 "diperbarui": sekarang()})
        except Exception as e:  # noqa
            log(f"[{jid}] gagal menulis status gagal: {scrub(e, kunci)}")

    try:
        lapor("Menyiapkan", 1)
        naskah = siapkan_naskah(job, kerja, rest, log)
        if tts == "gemini":
            kunci = rest.rpc("kunci_untuk_worker", {"p_user": uid, "p_penyedia": "gemini"})
            if not kunci:
                raise GalatPengguna("Kunci Gemini belum diisi. Buka Pengaturan, simpan kunci API Gemini, lalu buat video lagi.")
        hasil = jalankan.buat(naskah, dasar=kerja, kerja=kerja / "kerja", keluar=kerja / "video.mp4", tts=tts,
                              kunci_gemini=kunci, lapor=lapor, opsi_tts=opsi_tts)
        lapor("Mengunggah hasil", 96)
        pv, pk = f"{uid}/{jid}.mp4", f"{uid}/{jid}-kontak.png"
        rest.unggah("hasil", pv, hasil["keluar"], "video/mp4")
        if hasil["kontak"]:
            rest.unggah("hasil", pk, hasil["kontak"], "image/png")
        catatan = "; ".join(hasil["peringatan"])[:300] or None
        rest.patch_job(jid, {"status": "selesai", "progres": 100, "tahap": "Selesai", "pesan": catatan, "hasil_path": pv,
                             "kontak_path": pk if hasil["kontak"] else None, "durasi": hasil["durasi"],
                             "selesai": sekarang(), "diperbarui": sekarang()})
        log(f"[{jid}] selesai ({hasil['durasi']} dtk)")
    except (GalatPengguna, jalankan.GalatNaskah) as e:
        log(f"[{jid}] ditolak: {scrub(e, kunci)}")
        gagal(str(e))
    except TTSGalat as e:
        log(f"[{jid}] galat suara: {scrub(e, kunci)}")
        gagal(f"Pembuatan suara gagal: {scrub(e, kunci)}")
    except Exception as e:  # noqa
        log(f"[{jid}] galat tak terduga: {scrub(traceback.format_exc(), kunci)}")
        gagal("Terjadi kesalahan saat memproses video. Coba lagi; jika terulang, hubungi admin.")
    finally:
        shutil.rmtree(kerja, ignore_errors=True)


def bersihkan_lama(rest, hari=7, log=print):
    """Hapus berkas hasil yang lebih tua dari `hari` hari (video besar tidak disimpan selamanya)."""
    n = 0
    for j in rest.rpc("daftar_job_kedaluwarsa", {"p_hari": hari}) or []:
        paths = [p for p in (j.get("hasil_path"), j.get("kontak_path")) if p]
        rest.hapus("hasil", paths)
        rest.patch_job(j["id"], {"hasil_path": None, "kontak_path": None,
                                 "pesan": f"Berkas dihapus otomatis setelah {hari} hari."})
        n += 1
    if n:
        log(f"dibersihkan: {n} job")
    return n

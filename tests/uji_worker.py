"""Uji worker server dengan Supabase dan Gemini palsu (HTTP lokal). Tidak butuh jaringan.
Jalankan: python3 tests/uji_worker.py"""
import base64
import io
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from PIL import Image

from worker import main as worker_main
from worker import proses
from worker.rest import Rest

UID, UID2 = str(uuid.uuid4()), str(uuid.uuid4())
KUNCI_USER = "AIzaSyKUNCI-RAHASIA-USER-0001-abcdefghij"
hasil = []


class S:  # keadaan server palsu
    jobs, kunci, storage, log, patches, gemini_req = {}, {}, {}, [], [], []
    gemini_mode, pulih_panggilan, kedaluwarsa, flaky = "ok", 0, [], 0


def reset():
    S.jobs, S.kunci, S.storage, S.log, S.patches, S.gemini_req = {}, {}, {}, [], [], []
    S.gemini_mode, S.pulih_panggilan, S.kedaluwarsa, S.flaky = "ok", 0, [], 0
    S.kunci[(UID, "gemini")] = KUNCI_USER


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _isi(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _kirim(self, kode, data=b"", tipe="application/json"):
        b = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.send_response(kode); self.send_header("Content-Type", tipe); self.send_header("Content-Length", str(len(b))); self.end_headers()
        self.wfile.write(b)

    def _cek_auth(self):
        return self.headers.get("apikey") == "kunci-layanan-uji" and self.headers.get("Authorization") == "Bearer kunci-layanan-uji"

    def do_POST(self):
        p, isi = self.path, self._isi()
        S.log.append(("POST", p))
        if "generateContent" in p:
            req = json.loads(isi); S.gemini_req.append({"kunci": self.headers.get("x-goog-api-key"), "teks": req["contents"][0]["parts"][0]["text"]})
            if S.gemini_mode == "429":
                return self._kirim(429, {"error": {"message": "kuota"}})
            if S.gemini_mode == "400_ekor_kunci":
                return self._kirim(400, {"error": {"message": "API key not valid: " + (self.headers.get("x-goog-api-key") or "")}})
            kata = len(S.gemini_req[-1]["teks"].split())
            n = int(24000 * max(2.0, kata * 0.22))
            pcm = b"".join(int(8000 * math.sin(2 * math.pi * 220 * i / 24000)).to_bytes(2, "little", signed=True) for i in range(n))
            return self._kirim(200, {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "audio/L16;codec=pcm;rate=24000", "data": base64.b64encode(pcm).decode()}}]}}]})
        if not self._cek_auth():
            return self._kirim(401, {"message": "kunci layanan salah"})
        if p.startswith("/rest/v1/rpc/"):
            fn, a = p.rsplit("/", 1)[1], (json.loads(isi) if isi else {})
            if fn == "ambil_job_berikutnya":
                if S.flaky:
                    S.flaky -= 1; return self._kirim(503, {"message": "sementara"})
                for j in S.jobs.values():
                    if j["status"] == "antri":
                        j["status"] = "berjalan"; j["worker"] = a["p_worker"]; return self._kirim(200, [j])
                return self._kirim(200, [])
            if fn == "kunci_untuk_worker":
                return self._kirim(200, S.kunci.get((a["p_user"], a["p_penyedia"])))
            if fn == "pulihkan_job_macet":
                S.pulih_panggilan += 1; return self._kirim(200, 0)
            if fn == "daftar_job_kedaluwarsa":
                return self._kirim(200, S.kedaluwarsa)
            return self._kirim(404, {"message": "rpc tidak dikenal"})
        if p.startswith("/storage/v1/object/hasil/"):
            S.storage[("hasil", p.split("/storage/v1/object/hasil/", 1)[1])] = isi
            return self._kirim(200, {"Key": "ok"})
        self._kirim(404, {})

    def do_PATCH(self):
        isi = self._isi(); S.log.append(("PATCH", self.path))
        if not self._cek_auth():
            return self._kirim(401, {})
        m = re.search(r"id=eq\.([0-9a-f-]{36})", self.path)
        d = json.loads(isi); S.patches.append((m.group(1), d)); S.jobs[m.group(1)].update(d)
        self._kirim(204)

    def do_GET(self):
        S.log.append(("GET", self.path))
        if not self._cek_auth():
            return self._kirim(401, {})
        pre = "/storage/v1/object/authenticated/unggahan/"
        if self.path.startswith(pre):
            from urllib.parse import unquote
            b = S.storage.get(("unggahan", unquote(self.path[len(pre):])))
            return self._kirim(200, b, "application/octet-stream") if b is not None else self._kirim(404, {"message": "Object not found"})
        self._kirim(404, {})

    def do_DELETE(self):
        isi = json.loads(self._isi() or b"{}"); S.log.append(("DELETE", self.path))
        for pth in isi.get("prefixes", []):
            S.storage.pop((self.path.rsplit("/", 1)[1], pth), None)
        self._kirim(200, [])


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{srv.server_port}"
os.environ["GEMINI_BASE_URL"] = BASE + "/v1beta"
REST = Rest(BASE, "kunci-layanan-uji", timeout=20)
OPSI_CEPAT = {"coba": 2, "jeda_awal": 0.01}


def uji(nama, fn):
    try:
        fn(); hasil.append(True); print("LOLOS  " + nama)
    except Exception as e:  # noqa
        import traceback
        hasil.append(False); print("GAGAL  " + nama + f"\n        {type(e).__name__}: {e}\n" + "".join("        " + l for l in traceback.format_exc().splitlines(True)[-4:]))


def png(w=320, h=200, mode="RGB"):
    b = io.BytesIO(); Image.new(mode, (w, h), (200, 120, 60) if mode == "RGB" else 0).save(b, "PNG"); return b.getvalue()


def naskah(gambar=None, **ekstra):
    b = [{"tipe": "hook", "teks": ["Tes *hook*"], "ucapan": "Ini hook uji."}]
    if gambar:
        b.append({"tipe": "gambar", "file": gambar, "teks": "Gambar uji", "ucapan": "Ini gambar uji."})
    b.append({"tipe": "penutup", "teks": ["Selesai"], "ucapan": "Sampai jumpa."})
    n = {"judul": "Uji", "style": "kartun-hangat", "voice": "Kore", "bagian": b}
    n.update(ekstra); return n


def antri(n, user=UID):
    jid = str(uuid.uuid4())
    S.jobs[jid] = {"id": jid, "user_id": user, "status": "berjalan", "naskah": n, "progres": 0}
    return jid


def jalan(jid, tts="gemini", log=None):
    logs = [] if log is None else log
    proses.proses_job(REST, S.jobs[jid], tts=tts, opsi_tts=OPSI_CEPAT, log=logs.append)
    return S.jobs[jid], logs


def ffprobe(b):
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(b); n = f.name
    try:
        return json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", n], capture_output=True, text=True).stdout)["streams"]
    finally:
        os.unlink(n)


def gagal_dengan(n, potong, user=UID, **kw):
    reset(); j, logs = jalan(antri(n, user), **kw)
    assert j["status"] == "gagal", j
    assert potong.lower() in j["pesan"].lower(), j["pesan"]
    return j, logs


# ------------------------------------------------------------------ sukses
def t_sukses():
    reset()
    S.storage[("unggahan", f"{UID}/foto.png")] = png()
    jid = antri(naskah(f"unggahan:{UID}/foto.png"))
    jam = sorted(os.listdir(tempfile.gettempdir()))
    j, logs = jalan(jid)
    assert j["status"] == "selesai" and j["progres"] == 100, j
    assert j["hasil_path"] == f"{UID}/{jid}.mp4" and j["kontak_path"] == f"{UID}/{jid}-kontak.png"
    mp4 = S.storage[("hasil", j["hasil_path"])]
    st = {s["codec_type"]: s for s in ffprobe(mp4)}
    assert st["video"]["codec_name"] == "h264" and st["video"]["pix_fmt"] == "yuv420p" and st["video"]["avg_frame_rate"] == "30/1" and "audio" in st
    assert S.storage[("hasil", j["kontak_path"])][:4] == b"\x89PNG"
    assert S.gemini_req[0]["kunci"] == KUNCI_USER, "harus memakai kunci milik pemilik job"
    assert "Ini hook uji" in S.gemini_req[0]["teks"]
    pr = [d["progres"] for _, d in S.patches if "progres" in d and "status" not in d]
    assert pr == sorted(pr) and max(pr) >= 90 and any(d.get("tahap") == "Merender video" for _, d in S.patches)
    semua = json.dumps(S.patches) + "\n".join(logs)
    assert KUNCI_USER not in semua, "kunci API bocor ke patch/log"
    sisa = [d for d in os.listdir(tempfile.gettempdir()) if d.startswith(f"job-{jid[:8]}")]
    assert not sisa, f"folder kerja tidak dibersihkan: {sisa}"
    assert j["durasi"] and j["durasi"] > 1.5


# ------------------------------------------------------------------ penolakan (keamanan dan validasi)
def t_tanpa_kunci():
    reset(); S.kunci.clear()
    j, _ = jalan(antri(naskah())); assert j["status"] == "gagal" and "Kunci Gemini belum diisi" in j["pesan"]


def t_gambar_user_lain():
    reset(); S.storage[("unggahan", f"{UID2}/rahasia.png")] = png()
    j, _ = jalan(antri(naskah(f"unggahan:{UID2}/rahasia.png")))
    assert j["status"] == "gagal" and "tidak diizinkan" in j["pesan"]
    assert not any("rahasia.png" in p for m, p in S.log if m == "GET"), "worker tidak boleh mengambil berkas milik user lain"


def t_jalur_lokal():
    for f in ("aset/x.png", "/etc/passwd", "../../etc/passwd", "file:///etc/passwd", "unggahan:" + UID + "/../x.png",
              f"unggahan:{UID}/a/b.png", f"unggahan:{UID}/.rahasia", "http://evil.example/x.png"):
        reset(); j, _ = jalan(antri(naskah(f)))
        assert j["status"] == "gagal" and "tidak diizinkan" in j["pesan"], (f, j["pesan"])
        assert not [1 for m, p in S.log if m == "GET"], f"tidak boleh ada unduhan untuk {f}"


def t_bom_gambar():
    reset(); S.storage[("unggahan", f"{UID}/bom.png")] = png(20000, 20000, "1")
    j, _ = jalan(antri(naskah(f"unggahan:{UID}/bom.png"))); assert j["status"] == "gagal" and "terlalu besar" in j["pesan"], j["pesan"]


def t_bukan_gambar():
    reset(); S.storage[("unggahan", f"{UID}/x.png")] = b"<?php echo 1; ?>" * 10
    j, _ = jalan(antri(naskah(f"unggahan:{UID}/x.png"))); assert j["status"] == "gagal" and "bukan gambar" in j["pesan"]


def t_gambar_gif_ditolak():
    reset(); b = io.BytesIO(); Image.new("P", (10, 10)).save(b, "GIF"); S.storage[("unggahan", f"{UID}/a.png")] = b.getvalue()
    j, _ = jalan(antri(naskah(f"unggahan:{UID}/a.png"))); assert j["status"] == "gagal" and "PNG, JPEG, atau WEBP" in j["pesan"]


def t_gambar_9mb():
    reset(); S.storage[("unggahan", f"{UID}/besar.png")] = b"\x89PNG" + b"0" * (9 * 1024 * 1024)
    j, _ = jalan(antri(naskah(f"unggahan:{UID}/besar.png"))); assert j["status"] == "gagal" and "8 MB" in j["pesan"], j["pesan"]


def t_gambar_hilang():
    gagal_dengan(naskah(f"unggahan:{UID}/tidakada.png"), "tidak ditemukan")


def t_naskah_tanpa_ucapan():
    n = naskah(); del n["bagian"][0]["ucapan"]; gagal_dengan(n, "ucapan")


def t_style_asing():
    gagal_dengan(naskah(style="../../etc/passwd"), "Style tidak dikenal")


def t_terlalu_panjang():
    n = naskah(); n["bagian"][0]["ucapan"] = " ".join(["kata"] * 460); gagal_dengan(n, "maksimal 450 kata")


def t_string_raksasa():
    n = naskah(); n["bagian"][0]["teks"] = ["x" * 5000]; gagal_dengan(n, "lebih dari 500 karakter")


def t_terlalu_banyak_bagian():
    n = naskah(); n["bagian"] = n["bagian"] * 30; gagal_dengan(n, "Maksimal 40 bagian")


def t_banyak_bagian_sah_tidak_ditolak():
    # 15 bagian (lebih dari batas daftar umum 12) dan satu kalimat VO panjang (>500 karakter) adalah naskah yang wajar
    n = naskah(); n["bagian"] = [dict(n["bagian"][0]) for _ in range(15)]
    n["bagian"][1]["ucapan"] = " ".join(["kata"] * 120)
    with tempfile.TemporaryDirectory() as d:
        r = proses.siapkan_naskah({"user_id": UID, "naskah": n}, Path(d), REST)
    assert len(r["bagian"]) == 15 and len(r["bagian"][1]["ucapan"]) > 500


def t_tipe_asing():
    n = naskah(); n["bagian"][0]["tipe"] = "shell"; gagal_dengan(n, "jenis bagian tidak dikenal")


def t_sanitasi():
    reset(); n = naskah(); n["bagian"].insert(1, {"tipe": "angka", "nilai": 5, "desimal": 10 ** 9, "label": "x", "sumber": "s", "ucapan": "Angka lima."})
    n["musik"] = "/etc/passwd"; n["audio"] = "/etc/passwd"; n["akun"] = "@a\x00b\x07" + "z" * 100; n["voice"] = "../../x"
    with tempfile.TemporaryDirectory() as d:
        r = proses.siapkan_naskah({"user_id": UID, "naskah": n}, Path(d), REST)
    assert r["bagian"][1]["desimal"] == 6 and "musik" not in r and "audio" not in r
    assert r["voice"] == "Kore" and len(r["akun"]) <= 40 and "\x00" not in r["akun"]


def t_nilai_tak_wajar():
    n = naskah(); n["bagian"].insert(1, {"tipe": "angka", "nilai": 1e30, "label": "x", "ucapan": "Angka."}); gagal_dengan(n, "angka yang tidak wajar")


def t_gemini_429():
    reset(); S.gemini_mode = "429"
    j, _ = jalan(antri(naskah())); assert j["status"] == "gagal" and "kuota" in j["pesan"].lower() and "Pembuatan suara gagal" in j["pesan"], j["pesan"]


def t_kunci_tidak_bocor_lewat_galat():
    reset(); S.gemini_mode = "400_ekor_kunci"
    j, logs = jalan(antri(naskah()))
    assert j["status"] == "gagal"
    teks = json.dumps(S.patches) + "\n".join(logs) + j["pesan"]
    assert KUNCI_USER not in teks and "***" in j["pesan"], j["pesan"]


def t_batas_waktu():
    reset(); old = proses.BATAS["waktu_detik"]; proses.BATAS["waktu_detik"] = -1
    try:
        j, _ = jalan(antri(naskah()))
    finally:
        proses.BATAS["waktu_detik"] = old
    assert j["status"] == "gagal" and "batas waktu" in j["pesan"]


def t_galat_tak_terduga_tidak_membocorkan_detail():
    reset(); S.kunci[(UID, "gemini")] = KUNCI_USER
    asli = proses.jalankan.buat
    def rusak(*a, **k): raise RuntimeError(f"gagal di /home/rahasia/jalur dengan {KUNCI_USER}")
    proses.jalankan.buat = rusak
    try:
        j, logs = jalan(antri(naskah()))
    finally:
        proses.jalankan.buat = asli
    assert j["status"] == "gagal" and "/home/rahasia" not in j["pesan"] and KUNCI_USER not in j["pesan"] and "hubungi admin" in j["pesan"]
    assert KUNCI_USER not in "\n".join(logs)


# ------------------------------------------------------------------ antrian dan perawatan
def t_loop_sekali():
    reset(); a, b = antri(naskah(), UID), antri(naskah(), UID)
    S.jobs[a]["status"] = S.jobs[b]["status"] = "antri"
    rc = worker_main.main(["--sekali"], rest=REST, tts="gemini", opsi_tts=OPSI_CEPAT)
    assert rc == 0 and S.jobs[a]["status"] == "selesai" and S.jobs[b]["status"] == "selesai"
    assert S.pulih_panggilan == 1, "pemulihan job macet harus dipanggil"
    assert S.jobs[a]["worker"]


def t_retry_rest():
    reset(); S.flaky = 1
    j = worker_main.ambil_job(REST, "w1"); assert j is None   # 503 sekali lalu pulih (retry)


def t_bersihkan():
    reset(); jid = antri(naskah())
    S.jobs[jid].update(status="selesai", hasil_path=f"{UID}/{jid}.mp4", kontak_path=f"{UID}/{jid}-kontak.png")
    S.storage[("hasil", f"{UID}/{jid}.mp4")] = b"x"; S.storage[("hasil", f"{UID}/{jid}-kontak.png")] = b"y"
    S.kedaluwarsa = [dict(S.jobs[jid])]
    assert proses.bersihkan_lama(REST, 7, log=lambda *_: None) == 1
    assert not [k for k in S.storage if k[0] == "hasil"] and S.jobs[jid]["hasil_path"] is None and "dihapus" in S.jobs[jid]["pesan"]


def t_id_job_disuntik():
    for buruk in ("x&status=eq.selesai", "1; drop table job", "../x"):
        try:
            REST.patch_job(buruk, {}); raise AssertionError("id buruk diterima: " + buruk)
        except ValueError:
            pass


def t_tanpa_env():
    for k in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY"):
        os.environ.pop(k, None)
    assert worker_main.main(["--sekali"]) == 2


for nama, fn in [(n[2:].replace("_", " "), f) for n, f in sorted(globals().items()) if n.startswith("t_") and callable(f)]:
    uji(nama, fn)
srv.shutdown()
print(f"\n{sum(hasil)}/{len(hasil)} lolos")
sys.exit(0 if all(hasil) else 1)

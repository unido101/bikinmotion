"""Uji modul VO, timestamps, naskah Gemini, dan alur otomatis (tanpa jaringan sungguhan).
Jalankan dari akar repo: python3 tests/uji_lanjutan.py
Server Gemini palsu lokal dipakai untuk menguji jalur HTTP (sukses, 429 lalu ulang, 404)."""
import base64
import json
import os
import sys
import tempfile
import threading
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from pipeline import naskah_gemini, otomatis, selaras, susun, tts_gemini
from pipeline.tts_tiruan import sintesis_tiruan

hasil = []


def uji(nama):
    def deko(fn):
        try:
            fn()
            hasil.append((nama, True, ""))
        except Exception as e:  # noqa
            hasil.append((nama, False, f"{type(e).__name__}: {e}"))
        return fn
    return deko


# ---------------------------------------------------------------- selaras
@uji("selaraskan: kata cocok memakai waktu ASR, kata beda diinterpolasi")
def _():
    naskah = "Angka ini 42 persen dari total dunia".split()
    asr = [{"kata": "Angka", "mulai": 0.0, "selesai": 0.4}, {"kata": "ini", "mulai": 0.5, "selesai": 0.7},
           {"kata": "empat", "mulai": 0.8, "selesai": 1.0}, {"kata": "puluh", "mulai": 1.0, "selesai": 1.2},
           {"kata": "dua", "mulai": 1.2, "selesai": 1.4}, {"kata": "persen", "mulai": 1.5, "selesai": 2.0},
           {"kata": "dari", "mulai": 2.1, "selesai": 2.3}, {"kata": "total", "mulai": 2.4, "selesai": 2.8},
           {"kata": "dunia", "mulai": 2.9, "selesai": 3.3}]
    h = selaras.selaraskan(naskah, asr)
    assert h[0]["mulai"] == 0.0 and h[0]["cocok"], h[0]
    assert not h[2]["cocok"] and 0.7 <= h[2]["mulai"] <= 1.5, h[2]       # "42" diinterpolasi di antara "ini" dan "persen"
    assert h[3]["kata"] == "persen" and h[3]["mulai"] == 1.5 and h[3]["cocok"], h[3]
    assert all(a["mulai"] <= b["mulai"] for a, b in zip(h, h[1:])), "tidak monoton"


@uji("selaraskan: ASR kehilangan kata dan menambah kata sisipan")
def _():
    naskah = "satu dua tiga empat lima enam".split()
    asr = [{"kata": "satu", "mulai": 0, "selesai": 0.3}, {"kata": "eh", "mulai": 0.3, "selesai": 0.5},
           {"kata": "dua", "mulai": 0.6, "selesai": 0.9}, {"kata": "empat", "mulai": 1.8, "selesai": 2.1},
           {"kata": "lima", "mulai": 2.2, "selesai": 2.5}, {"kata": "enam", "mulai": 2.6, "selesai": 3.0}]
    h = selaras.selaraskan(naskah, asr)
    assert h[2]["cocok"] is False and 0.9 <= h[2]["mulai"] < 1.8                 # "tiga" hilang
    assert h[3]["mulai"] == 1.8


NASKAH_TES = ("Ini kalimat pertama untuk uji. Ini kalimat kedua yang sedikit lebih panjang. "
              "Dan ini kalimat ketiga sebagai penutup.")


@uji("dari_jeda: batas kalimat dari jeda audio dekat dengan waktu sebenarnya")
def _():
    kata = NASKAH_TES.split()
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "a.wav"
        tepat = sintesis_tiruan(kata, wav)
        est = selaras.dari_jeda(kata, wav)
    awal = [i for i, k in enumerate(kata) if i == 0 or kata[i - 1][-1] in ".!?"]
    for i in awal:
        assert abs(est[i]["mulai"] - tepat[i]["mulai"]) < 0.3, (i, est[i], tepat[i])


# ---------------------------------------------------------------- server Gemini palsu
class Palsu(BaseHTTPRequestHandler):
    permintaan = []
    perilaku = {}

    def log_message(self, *a):
        pass

    def do_POST(self):
        isi = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Palsu.permintaan.append({"path": self.path, "kunci": self.headers.get("x-goog-api-key"), "isi": isi})
        model = self.path.split("/models/")[1].split(":")[0]
        urut = sum(1 for p in Palsu.permintaan if model in p["path"])
        mode = Palsu.perilaku.get(model, "ok")
        if mode == "404":
            return self._kirim(404, {"error": {"message": "model tidak ditemukan"}})
        if mode == "429_lalu_ok" and urut == 1:
            return self._kirim(429, {"error": {"message": "kuota"}})
        if mode == "selalu429":
            return self._kirim(429, {"error": {"message": "kuota"}})
        if mode.startswith("naskah"):
            return self._kirim(200, {"candidates": [{"content": {"parts": [{"text": "```json\n" + json.dumps(NASKAH_PALSU[0 if (mode == "naskah_buruk_lalu_baik" and urut == 1) else 1]) + "\n```"}]}}]})
        import math
        pcm = b"".join(int(8000 * math.sin(2 * math.pi * 220 * i / 24000)).to_bytes(2, "little", signed=True) for i in range(24000))
        self._kirim(200, {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "audio/L16;codec=pcm;rate=24000", "data": base64.b64encode(pcm).decode()}}]}}]})

    def _kirim(self, kode, data):
        b = json.dumps(data).encode()
        self.send_response(kode)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)


NASKAH_PALSU = [
    {"judul": "buruk", "style": "bersih-edukasi", "bagian": [
        {"tipe": "hook", "teks": ["Hai"], "ucapan": "Hai semua."},
        {"tipe": "angka", "nilai": 5, "label": "x", "ucapan": "Angka lima."},   # tanpa sumber -> ditolak (ketat)
        {"tipe": "penutup", "teks": ["Bye"], "ucapan": "Sampai jumpa."}]},
    {"judul": "baik", "style": "bersih-edukasi", "bagian": [
        {"tipe": "hook", "teks": ["Hai"], "ucapan": "Hai semua, ini contoh."},
        {"tipe": "angka", "nilai": 5, "label": "x", "sumber": "FAKTA user", "ucapan": "Angka lima dari fakta user."},
        {"tipe": "penutup", "teks": ["Bye"], "ucapan": "Sampai jumpa."}]},
]

server = ThreadingHTTPServer(("127.0.0.1", 0), Palsu)
threading.Thread(target=server.serve_forever, daemon=True).start()
os.environ["GEMINI_BASE_URL"] = f"http://127.0.0.1:{server.server_port}/v1beta"
os.environ["GEMINI_API_KEY"] = "kunci-uji"


@uji("tts_gemini: 429 lalu berhasil, WAV 24 kHz mono, payload AUDIO + voice")
def _():
    Palsu.permintaan.clear()
    Palsu.perilaku = {"model-a": "429_lalu_ok"}
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "vo.wav"
        tts_gemini.sintesis("Halo dunia.", out, voice="Kore", model="model-a", jeda_awal=0.01)
        with wave.open(str(out)) as w:
            assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 24000)
            assert abs(w.getnframes() / 24000 - 1.0) < 0.01
    assert len(Palsu.permintaan) == 2, len(Palsu.permintaan)
    p = Palsu.permintaan[-1]
    assert p["kunci"] == "kunci-uji"
    g = p["isi"]["generationConfig"]
    assert g["responseModalities"] == ["AUDIO"]
    assert g["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == "Kore"
    assert "Halo dunia." in p["isi"]["contents"][0]["parts"][0]["text"]


@uji("tts_gemini: 404 memberi petunjuk nama model; 429 terus-menerus melapor kuota")
def _():
    Palsu.perilaku = {"model-404": "404", "model-429": "selalu429"}
    with tempfile.TemporaryDirectory() as d:
        try:
            tts_gemini.sintesis("x", Path(d) / "a.wav", model="model-404", jeda_awal=0.01)
            raise AssertionError("harus gagal")
        except tts_gemini.TTSGalat as e:
            assert "GEMINI_TTS_MODEL" in str(e)
        try:
            tts_gemini.sintesis("x", Path(d) / "b.wav", model="model-429", coba=2, jeda_awal=0.01)
            raise AssertionError("harus gagal")
        except tts_gemini.TTSGalat as e:
            assert "kuota" in str(e).lower()


@uji("naskah_gemini: naskah buruk ditolak, dikirim ulang dengan daftar masalah, hasil baik diterima")
def _():
    Palsu.permintaan.clear()
    Palsu.perilaku = {"model-n": "naskah_buruk_lalu_baik"}
    n, _ = naskah_gemini.buat_naskah("topik uji", fakta=["fakta A"], model="model-n")
    assert n["judul"] == "baik"
    assert len(Palsu.permintaan) == 2
    prompt2 = Palsu.permintaan[1]["isi"]["contents"][0]["parts"][0]["text"]
    assert "PERBAIKI" in prompt2 and "sumber" in prompt2
    prompt1 = Palsu.permintaan[0]["isi"]["contents"][0]["parts"][0]["text"]
    assert "fakta A" in prompt1 and "Jangan mengarang fakta" in prompt1


# ---------------------------------------------------------------- alur otomatis
NASKAH = ROOT / "examples" / "naskah.contoh.json"


@uji("otomatis: TTS tiruan -> MP4 lolos, scene bersambung, poin muncul sesuai kalimat")
def _():
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "v.mp4"
        rc = otomatis.main(["--naskah", str(NASKAH), "--tts", "tiruan", "--out", str(out)])
        assert rc == 0 and out.exists()
        tl = json.loads((Path(d) / "v_kerja" / "timeline.json").read_text())
        sc = tl["scene"]
        assert sc[0]["mulai"] == 0
        assert all(abs(a["selesai"] - b["mulai"]) < 1e-6 for a, b in zip(sc, sc[1:])), "scene tidak bersambung"
        poin = next(s for s in sc if s["tipe"] == "poin")
        assert poin["waktu"] == sorted(poin["waktu"]) and poin["waktu"][-1] > poin["waktu"][0] + 0.5, poin["waktu"]
        assert len(tl["subtitle"]) >= 6
        assert any(s["kata_kunci"] for s in tl["subtitle"])
        dur = selaras.durasi(out)
        assert abs(dur - sc[-1]["selesai"]) < 0.15, (dur, sc[-1]["selesai"])
        # VO user (audio tiruan yang sama) + selaras 'diam': waktu scene dekat dengan yang tepat
        out2 = Path(d) / "v2.mp4"
        rc2 = otomatis.main(["--naskah", str(NASKAH), "--audio", str(Path(d) / "v_kerja" / "vo.wav"),
                             "--selaras", "diam", "--out", str(out2)])
        assert rc2 == 0
        tl2 = json.loads((Path(d) / "v2_kerja" / "timeline.json").read_text())
        for a, b in zip(sc, tl2["scene"]):
            assert abs(a["mulai"] - b["mulai"]) < 0.5, (a["tipe"], a["mulai"], b["mulai"])


@uji("otomatis: naskah dengan [perlu verifikasi] atau angka tanpa sumber (ketat) ditolak sebelum render")
def _():
    n = json.loads(NASKAH.read_text())
    n["bagian"][0]["ucapan"] = "Klaim ini [perlu verifikasi] ya."
    g, _ = susun.cek_naskah(n)
    assert any("verifikasi" in x for x in g)
    n = json.loads(NASKAH.read_text())
    del n["bagian"][1]["sumber"]
    g, p = susun.cek_naskah(n)
    assert not g and any("sumber" in x for x in p)
    g, _ = susun.cek_naskah(n, ketat=True)
    assert any("sumber" in x for x in g)


server.shutdown()
gagal = 0
for nama, ok, ket in hasil:
    print(("LOLOS  " if ok else "GAGAL  ") + nama + (f"\n        {ket}" if ket else ""))
    gagal += not ok
print(f"\n{len(hasil) - gagal}/{len(hasil)} lolos")
sys.exit(1 if gagal else 0)

"""Membuat naskah.json dari topik memakai model teks Gemini (paket gratis).

Aturan fakta: model hanya boleh memakai FAKTA yang diberikan user. Angka, tanggal, nama, atau klaim
yang tidak ada di FAKTA tidak boleh dikarang; hasilnya diperiksa dan klaim bermasalah ditolak.
Env: GEMINI_API_KEY, GEMINI_TEXT_MODEL (cek model gratis terbaru di AI Studio), GEMINI_BASE_URL (uji).
"""
import json
import os
import re
import urllib.error
import urllib.request

from . import gaya as gaya_mod
from .susun import cek_naskah
from .tts_gemini import base_url

MODEL_TEKS_DEFAULT = "gemini-2.5-flash"

PROMPT = """Kamu penulis naskah video pendek (short form) berbahasa Indonesia.

TOPIK: {topik}

FAKTA YANG BOLEH DIPAKAI (satu-satunya sumber fakta):
{fakta}

ATURAN KERAS
1. Jangan mengarang fakta. Setiap angka, tanggal, nama, dan klaim harus berasal dari FAKTA di atas. Jika FAKTA kosong atau kurang, tulis naskah yang tidak memuat angka atau klaim spesifik dan isi "perlu_dicari" dengan fakta yang masih dibutuhkan.
2. Struktur: bagian pertama "hook" (kalimat pemancing, maksimal 3 detik), 3 sampai 5 bagian isi, bagian terakhir "penutup".
3. Total {kata} kata pada seluruh "ucapan" (sekitar {detik} detik). Kalimat lisan, pendek, satu ide per kalimat.
4. Jenis bagian yang tersedia dan field wajibnya:
   - hook: teks (daftar baris tampilan, maksimal 2 baris pendek)
   - angka: nilai (angka), label, opsional awalan, akhiran, desimal, sumber  (WAJIB isi sumber dari FAKTA)
   - poin: poin (daftar 2 sampai 4 poin pendek); ucapan berupa daftar kalimat, tepat satu per poin
   - bar: data (daftar {{label, nilai}}, 2 sampai 5 item), satuan, sumber (WAJIB)
   - penutup: teks (daftar baris), opsional ajakan
   Pakai angka dan bar hanya bila FAKTA memuat angkanya.
5. Setiap bagian punya "ucapan" (teks yang dibacakan, boleh berupa daftar kalimat untuk poin). Tanda *kata* menandai kata kunci subtitle.
6. Teks tampilan (teks, label, poin) lebih ringkas dari ucapan.
7. Style: pilih satu id dari: {styles}

KELUARAN: hanya JSON valid tanpa teks lain, bentuk:
{{"judul": "...", "style": "<id>", "bagian": [ {{"tipe": "hook", "teks": ["..."], "ucapan": "..."}}, ... ], "perlu_dicari": ["..."]}}
"""


class NaskahGalat(RuntimeError):
    pass


def _panggil(prompt, model, kunci):
    url = f"{base_url()}/models/{model}:generateContent"
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.6}}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": kunci})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        hint = " (kuota habis; coba lagi nanti)" if e.code == 429 else " (cek GEMINI_TEXT_MODEL)" if e.code in (400, 404) else ""
        raise NaskahGalat(f"Gemini HTTP {e.code}{hint}: {e.read().decode('utf-8', 'replace')[:200]}")
    parts = (((data.get("candidates") or [{}])[0].get("content") or {}).get("parts")) or []
    teks = "".join(p.get("text", "") for p in parts)
    teks = re.sub(r"^```(?:json)?\s*|\s*```$", "", teks.strip())
    try:
        return json.loads(teks)
    except json.JSONDecodeError as e:
        raise NaskahGalat(f"keluaran bukan JSON valid: {e}")


def buat_naskah(topik, fakta=(), durasi_detik=40, model=None, api_key=None):
    kunci = api_key or os.environ.get("GEMINI_API_KEY")
    if not kunci:
        raise NaskahGalat("GEMINI_API_KEY belum diisi")
    model = model or os.environ.get("GEMINI_TEXT_MODEL") or MODEL_TEKS_DEFAULT
    prompt = PROMPT.format(
        topik=topik,
        fakta="\n".join(f"- {f}" for f in fakta) if fakta else "(kosong)",
        kata=int(durasi_detik * 2.7), detik=durasi_detik,
        styles=", ".join(s["id"] for s in gaya_mod.daftar()))
    catatan = ""
    for percobaan in range(2):
        n = _panggil(prompt + catatan, model, kunci)
        galat, peringatan = cek_naskah(n, ketat=True)
        if not galat:
            return n, peringatan
        catatan = "\n\nPERBAIKI masalah ini lalu keluarkan JSON lengkap lagi:\n" + "\n".join(f"- {g}" for g in galat)
    raise NaskahGalat("naskah dari model tidak lolos pemeriksaan:\n" + "\n".join(galat))

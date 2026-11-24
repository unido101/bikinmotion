"""VO dari Gemini TTS lewat REST (generateContent, responseModalities AUDIO).

Respons berisi PCM mentah 16-bit mono (tanpa header WAV); laju sampel dibaca dari mimeType.
Env: GEMINI_API_KEY (wajib), GEMINI_TTS_MODEL (opsional), GEMINI_BASE_URL (untuk uji).
Nama model TTS Gemini masih berstatus preview dan berganti-ganti; ganti lewat env bila perlu.
"""
import base64
import json
import os
import re
import time
import urllib.error
import urllib.request
import wave

MODEL_DEFAULT = "gemini-3.1-flash-tts-preview"
GAYA_DEFAULT = "Bacakan dalam bahasa Indonesia dengan jelas, tenang, dan bertenaga"


class TTSGalat(RuntimeError):
    pass


def base_url():
    return os.environ.get("GEMINI_BASE_URL") or "https://generativelanguage.googleapis.com/v1beta"


def parse_rate(mime, default=24000):
    m = re.search(r"rate=(\d+)", mime or "")
    return int(m.group(1)) if m else default


def pcm_ke_wav(pcm, rate, path):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)


def bangun_payload(teks, voice, gaya):
    prompt = f"{gaya}: {teks}" if gaya else teks
    return {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }


def sintesis(teks, keluar, voice="Kore", gaya=GAYA_DEFAULT, model=None, api_key=None, coba=4, jeda_awal=4.0):
    """Satu permintaan per video (hemat kuota gratis). Return jalur WAV."""
    kunci = api_key or os.environ.get("GEMINI_API_KEY")
    if not kunci:
        raise TTSGalat("GEMINI_API_KEY belum diisi")
    model = model or os.environ.get("GEMINI_TTS_MODEL") or MODEL_DEFAULT
    url = f"{base_url()}/models/{model}:generateContent"
    isi = json.dumps(bangun_payload(teks, voice, gaya)).encode()
    terakhir = ""
    for i in range(coba):
        req = urllib.request.Request(url, data=isi, method="POST",
                                     headers={"Content-Type": "application/json", "x-goog-api-key": kunci})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read())
        except urllib.error.HTTPError as e:
            badan = e.read().decode("utf-8", "replace")[:300]
            terakhir = f"HTTP {e.code}: {badan}"
            if e.code == 429 or e.code >= 500:
                time.sleep(min(60, jeda_awal * 2 ** i))
                continue
            hint = " (cek nama model: set GEMINI_TTS_MODEL)" if e.code in (400, 404) else ""
            raise TTSGalat(f"Gemini TTS menolak permintaan. {terakhir}{hint}")
        parts = (((data.get("candidates") or [{}])[0].get("content") or {}).get("parts")) or []
        audio = next((p["inlineData"] for p in parts if "inlineData" in p), None)
        if not audio:
            raise TTSGalat(f"respons tanpa audio: {json.dumps(data)[:300]}")
        mentah = base64.b64decode(audio["data"])
        if mentah[:4] == b"RIFF":
            open(keluar, "wb").write(mentah)
        else:
            pcm_ke_wav(mentah, parse_rate(audio.get("mimeType")), keluar)
        return keluar
    raise TTSGalat(f"kuota atau laju habis setelah {coba} percobaan ({terakhir}). "
                   "Cek kuota proyek di AI Studio dan coba lagi nanti.")

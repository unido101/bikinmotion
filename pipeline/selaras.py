"""Timestamps kata. Mencocokkan kata naskah (yang pasti benar) dengan waktu dari ASR atau dari jeda audio.

Metode:
  whisper : faster-whisper dengan word timestamps, lalu dicocokkan ke kata naskah (paling akurat)
  diam    : deteksi jeda dengan ffmpeg silencedetect + pembagian proporsional (perkiraan)
"""
import difflib
import re
import subprocess


def norm(w):
    return re.sub(r"\W", "", w.lower())


def durasi(audio):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(audio)],
                                capture_output=True, text=True, check=True).stdout.strip())


def selaraskan(kata_naskah, asr):
    """kata_naskah: list str. asr: list {kata, mulai, selesai}. Return list per kata naskah
    {kata, mulai, selesai, cocok}. Kata yang tidak cocok diinterpolasi di antara kata cocok terdekat."""
    n = len(kata_naskah)
    if not asr:
        raise ValueError("hasil ASR kosong")
    a = [norm(w) for w in kata_naskah]
    b = [norm(x["kata"]) for x in asr]
    posisi = [None] * n
    for i, j, ukur in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(ukur):
            posisi[i + k] = (asr[j + k]["mulai"], asr[j + k]["selesai"])
    cocok = [p is not None for p in posisi]
    i = 0
    while i < n:
        if posisi[i] is not None:
            i += 1
            continue
        j = i
        while j < n and posisi[j] is None:
            j += 1
        t0 = posisi[i - 1][1] if i > 0 else asr[0]["mulai"]
        t1 = posisi[j][0] if j < n else asr[-1]["selesai"]
        if t1 <= t0:
            t1 = t0 + 0.12 * (j - i)
        bobot = [len(a[k]) + 1 for k in range(i, j)]
        total, acc = sum(bobot), t0
        for k, w in zip(range(i, j), bobot):
            dt = (t1 - t0) * w / total
            posisi[k] = (acc, acc + dt)
            acc += dt
        i = j
    hasil, prev = [], 0.0
    for k in range(n):
        m, s = posisi[k]
        m = max(m, prev)
        s = max(s, m + 0.02)
        hasil.append({"kata": kata_naskah[k], "mulai": round(m, 3), "selesai": round(s, 3), "cocok": cocok[k]})
        prev = m
    return hasil


def asr_whisper(audio, ukuran="small", bahasa="id"):
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise RuntimeError("faster-whisper belum terpasang (pip install faster-whisper)") from e
    model = WhisperModel(ukuran, device="cpu", compute_type="int8")
    segmen, _ = model.transcribe(str(audio), language=bahasa, word_timestamps=True)
    return [{"kata": w.word.strip(), "mulai": w.start, "selesai": w.end} for s in segmen for w in (s.words or []) if w.word.strip()]


def segmen_suara(audio, noise="-35dB", d=0.25):
    """Interval non-diam [(mulai, selesai)] lewat ffmpeg silencedetect."""
    total = durasi(audio)
    p = subprocess.run(["ffmpeg", "-i", str(audio), "-af", f"silencedetect=noise={noise}:d={d}", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    mulai = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", p.stderr)]
    akhir = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", p.stderr)]
    diam = list(zip(mulai, akhir + [total] * (len(mulai) - len(akhir))))
    seg, kursor = [], 0.0
    for m, e in diam:
        if m - kursor > 0.05:
            seg.append((kursor, m))
        kursor = e
    if total - kursor > 0.05:
        seg.append((kursor, total))
    return seg


def _bobot(kata):
    w = len(norm(kata)) + 1
    return w + (5 if kata[-1:] in ".!?" else 2 if kata[-1:] in ",;:" else 0)


def _bagi(kata, t0, t1):
    bobot = [_bobot(k) for k in kata]
    total, acc, out = sum(bobot), t0, []
    for k, w in zip(kata, bobot):
        dt = (t1 - t0) * w / total
        out.append({"kata": k, "mulai": round(acc, 3), "selesai": round(acc + dt * 0.92, 3), "cocok": False})
        acc += dt
    return out


def dari_jeda(kata_naskah, audio):
    """Perkiraan tanpa ASR. Bila jumlah segmen suara = jumlah kalimat, tiap kalimat dibagi di segmennya;
    jika tidak, seluruh kata dibagi proporsional di rentang suara."""
    seg = segmen_suara(audio)
    if not seg:
        raise RuntimeError("tidak ada suara terdeteksi di audio")
    kalimat, cur = [], []
    for k in kata_naskah:
        cur.append(k)
        if k[-1:] in ".!?":
            kalimat.append(cur)
            cur = []
    if cur:
        kalimat.append(cur)
    if len(seg) == len(kalimat):
        hasil = []
        for kal, (m, e) in zip(kalimat, seg):
            hasil += _bagi(kal, m, e)
        return hasil
    return _bagi(kata_naskah, seg[0][0], seg[-1][1])


def hitung(kata_naskah, audio, metode="auto", ukuran_whisper="small"):
    """Return (kata_berwaktu, metode_dipakai, akurat)."""
    if metode in ("auto", "whisper"):
        try:
            return selaraskan(kata_naskah, asr_whisper(audio, ukuran_whisper)), "whisper", True
        except RuntimeError as e:
            if metode == "whisper":
                raise
            print(f"  whisper tidak tersedia ({e}); memakai perkiraan dari jeda audio")
    return dari_jeda(kata_naskah, audio), "diam", False

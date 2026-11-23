"""Worker: mengambil job dari antrian dan memprosesnya.

  python -m worker.main               # berjalan terus (VPS / container)
  python -m worker.main --sekali      # kosongkan antrian lalu berhenti (Cloud Run Job + Scheduler)

Variabel lingkungan:
  SUPABASE_URL, SUPABASE_SERVICE_KEY   wajib. Kunci layanan = RAHASIA, hanya di server ini.
  WORKER_ID            nama worker (bawaan: hostname)
  WORKER_POLL_DETIK    jeda saat antrian kosong (bawaan 5)
  WORKER_SIMPAN_HARI   lama hasil disimpan (bawaan 7)
  WORKER_MODE_UJI=1    memakai suara tiruan (HANYA untuk uji; jangan di produksi)
"""
import argparse
import os
import signal
import socket
import sys
import time

from .proses import bersihkan_lama, proses_job
from .rest import Rest, RestGalat

BERHENTI = {"ya": False}


def ambil_job(rest, id_worker):
    hasil = rest.rpc("ambil_job_berikutnya", {"p_worker": id_worker})
    if isinstance(hasil, list):
        return hasil[0] if hasil else None
    return hasil or None


def main(argv=None, rest=None, tts=None, opsi_tts=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--sekali", action="store_true", help="proses semua job yang antri lalu berhenti")
    ap.add_argument("--poll", type=float, default=float(os.environ.get("WORKER_POLL_DETIK", "5")))
    a = ap.parse_args(argv)
    for f in (sys.stdout, sys.stderr):
        try:
            f.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        except Exception:
            pass

    if rest is None:
        url, kunci = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_KEY")
        if not url or not kunci:
            print("SUPABASE_URL dan SUPABASE_SERVICE_KEY wajib diisi.", file=sys.stderr)
            return 2
        rest = Rest(url, kunci)
    tts = tts or ("tiruan" if os.environ.get("WORKER_MODE_UJI") == "1" else "gemini")
    id_worker = os.environ.get("WORKER_ID") or socket.gethostname()
    simpan = int(os.environ.get("WORKER_SIMPAN_HARI", "7"))
    signal.signal(signal.SIGTERM, lambda *_: BERHENTI.update(ya=True))
    print(f"worker {id_worker} mulai (mode {'sekali' if a.sekali else 'terus'}, suara: {tts})", flush=True)

    t_pulih = t_bersih = 0.0
    jeda = a.poll
    while not BERHENTI["ya"]:
        try:
            t = time.time()
            if t - t_pulih > 60:
                t_pulih = t
                rest.rpc("pulihkan_job_macet", {"p_menit": 15})
            if t - t_bersih > 6 * 3600:
                t_bersih = t
                bersihkan_lama(rest, simpan)
            job = ambil_job(rest, id_worker)
        except RestGalat as e:
            print(f"galat koneksi ke Supabase: {e}", file=sys.stderr, flush=True)
            if a.sekali:
                return 1
            time.sleep(min(60, jeda * 4))
            continue
        if job:
            proses_job(rest, job, id_worker=id_worker, tts=tts, opsi_tts=opsi_tts)
            jeda = a.poll
            continue
        if a.sekali:
            break
        time.sleep(jeda)
        jeda = min(30, jeda * 1.5)
    print("worker berhenti", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

# Worker: tempat video dirender

Worker adalah program server yang mengambil job dari antrian Supabase, merender video dengan kunci API milik
pemilik job, lalu mengunggah hasilnya. Pengguna hanya memakai situs web; tidak ada yang dipasang di komputer mereka.

```
Browser (Vercel)  ->  Supabase: tabel job, Vault (kunci), Storage (gambar, hasil)  <-  Worker (server ini)
```

## Yang dibutuhkan worker

| Variabel | Isi |
|----------|-----|
| `SUPABASE_URL` | Project URL |
| `SUPABASE_SERVICE_KEY` | Kunci **secret / service_role**. RAHASIA: melewati semua aturan akses. Hanya di server worker. |
| `WORKER_ID` | (opsional) nama worker |
| `WORKER_SIMPAN_HARI` | (opsional) lama hasil disimpan, bawaan 7 |
| `WORKER_POLL_DETIK` | (opsional) jeda saat antrian kosong, bawaan 5 |

Jangan pernah menaruh kunci layanan di repo, di `web/`, atau di Vercel (situs).

## Pilihan tempat menjalankan

**1. Komputermu sendiri, untuk uji dan pemakaian pribadi (gratis).** Pengguna tetap tidak perlu memasang apa pun; hanya komputer
yang menjalankan worker yang butuh Python dan ffmpeg, dan komputer itu harus menyala saat ada video yang dibuat.

```powershell
py -m pip install -r requirements.txt
$env:SUPABASE_URL = "https://xxxx.supabase.co"
$env:SUPABASE_SERVICE_KEY = "kunci-secret"
py -m worker.main
```

**2. VPS kecil yang menyala terus (disarankan untuk dipakai orang lain).** Di server dengan Docker:

```bash
docker build -f worker/Dockerfile -t bikinmotion-worker .          # tambah --build-arg WHISPER=1 untuk sinkron per kata
docker run -d --restart unless-stopped --name worker \
  -e SUPABASE_URL=... -e SUPABASE_SERVICE_KEY=... bikinmotion-worker
```

**3. Cloud Run Job + Cloud Scheduler.** Worker mendukung `--sekali` (kosongkan antrian lalu berhenti), jadi bisa dijalankan terjadwal.
Catatan biaya: tiap eksekusi kosong tetap memakai waktu CPU, jadi jadwal yang terlalu rapat memboroskan jatah gratis, sedangkan jadwal
yang jarang membuat pengguna menunggu lebih lama. Perintah `gcloud`-nya belum saya uji; ikuti dokumentasi Google Cloud Run Jobs.

## Perilaku

- Satu job pada satu waktu per worker. Worker kedua aman dijalankan paralel (pengambilan job memakai `FOR UPDATE SKIP LOCKED`).
- Job yang macet (worker mati) diulang sekali, lalu dinyatakan gagal. Hasil lebih dari `WORKER_SIMPAN_HARI` hari dihapus otomatis.
- Batas per video: 450 kata VO, 40 bagian, 12 gambar (maks 8 MB, PNG/JPEG/WEBP), 20 menit pemrosesan.
  Batas per akun (2 video aktif, 20 per 24 jam) ada di `supabase/job.sql`.
- Gambar hanya boleh berasal dari penyimpanan milik pemilik job; jalur berkas lokal dan gambar milik akun lain ditolak.
- Kunci API pengguna dibaca hanya saat memproses job milik pengguna itu, tidak pernah ditulis ke log, pesan galat, atau tabel job.

## Uji

`python tests/uji_worker.py` menguji worker terhadap Supabase dan Gemini palsu (termasuk serangan: gambar milik akun lain, jalur lokal,
gambar bomb, kebocoran kunci lewat pesan galat). Yang belum teruji: koneksi ke Supabase dan Gemini sungguhan, dan image Docker.

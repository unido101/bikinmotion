# Video Studio

Membuat video motion graphic pendek (9:16, 30 fps) **lewat kode**: timeline JSON + style + audio VO menjadi MP4.
Semua frame dihitung oleh kode (Pillow + numpy), lalu dirakit dengan ffmpeg.

## Status

| Bagian | Status |
|--------|--------|
| Sistem style: 10 style dalam 3 keluarga (2D flat, pixel art, 3D), galeri, preview, template | Jadi dan teruji |
| Pustaka scene, renderer, validator, rakit MP4, cek otomatis | Jadi dan teruji |
| Penyusun timeline dari naskah + timestamps kata (`susun.py`) | Jadi dan teruji |
| Penyelaras timestamps: pencocokan ke kata naskah, perkiraan dari jeda audio | Jadi dan teruji |
| TTS Gemini (REST): jalur sukses, 429 lalu ulang, 404 | Teruji dengan server palsu lokal; **belum dengan API sungguhan** |
| Pembuat naskah Gemini (`buat_naskah`) dengan penolakan klaim tanpa sumber | Teruji dengan server palsu lokal; **belum dengan API sungguhan** |
| Whisper (faster-whisper) | Kode ada; **belum dijalankan** (tidak terpasang di lingkungan uji) |
| Halaman web (`web/`): galeri 10 style, penyusun naskah, petunjuk menjalankan | Jadi dan teruji di browser (desktop dan ponsel) |
| Login Supabase, persetujuan admin, masa aktif (halaman dan alur) | Teruji di browser dengan stub Supabase; **belum dengan Supabase sungguhan** |
| Skema basis data dan aturan RLS (`supabase/`) | Ditulis, **belum dijalankan** (tidak ada Postgres di lingkungan uji); jalankan `uji_rls.sql` |

## Pemakaian lokal

Butuh Python 3.10+, ffmpeg, dan `pip install -r requirements.txt`.

```bash
python3 tests/uji_dasar.py                       # uji asap semua style dan scene
python3 -m pipeline.preview                      # buat/ulang styles/<id>/preview.png
python3 -m pipeline.buat_video \
  --timeline examples/timeline.contoh.json \
  --audio vo.wav --out hasil/video.mp4           # video final (durasi = VO + 0,5 s)
```

Tanpa `--audio` hasilnya **draft bisu** untuk cek tata letak, bukan video final. Keluaran lain: `hasil/video.kontak.png` (lembar kontak untuk cek visual).

## Alur otomatis: naskah -> VO -> timestamps -> MP4

```bash
export GEMINI_API_KEY=...                 # kunci dari AI Studio (paket gratis)
python3 -m pipeline.buat_naskah --topik "Topik" --fakta fakta.txt --out naskah.json   # lalu baca dan setujui
python3 -m pipeline.otomatis --naskah naskah.json --out hasil/video.mp4
python3 -m pipeline.otomatis --naskah naskah.json --audio vo.wav --out hasil/video.mp4   # pakai VO sendiri
python3 -m pipeline.otomatis --naskah examples/naskah.contoh.json --tts tiruan --out hasil/uji.mp4   # uji tanpa jaringan
```

Format naskah dijelaskan di `pipeline/susun.py` (contoh: `examples/naskah.contoh.json`). Pembuatan naskah hanya boleh memakai
fakta dari `fakta.txt`; klaim tanpa sumber, angka tanpa `sumber`, dan teks bertanda `[perlu verifikasi]` ditolak sebelum render.

Catatan paket gratis Gemini: buat VO **sekali per video** (kuota TTS gratis sempit dan dihitung per proyek, cek di AI Studio),
dan isi naskah di paket gratis dapat dipakai Google untuk meningkatkan produknya, jadi jangan memasukkan data pribadi.
Nama model bisa diganti lewat env `GEMINI_TTS_MODEL` dan `GEMINI_TEXT_MODEL` (model preview sering berganti nama).

Timestamps: dengan `faster-whisper` terpasang (`pip install faster-whisper`) metode `whisper` memberi sinkron per kata.
Tanpa itu, `diam` memperkirakan dari jeda audio dan alur memberi peringatan bahwa sinkron hanya perkiraan.

## Halaman web (Vercel)

Folder `web/` adalah situs statis tanpa build: galeri style dengan pratinjau nyata, penyusun `naskah.json`
(dengan pemeriksaan aturan yang sama persis seperti di Python), dan petunjuk menjalankan. Render tetap
dikerjakan di komputermu; halaman ini tidak memanggil API apa pun dan tidak menyimpan kunci.

**Deploy ke Vercel.** Repo ini berisi kode Python di akar, jadi Vercel perlu diberi tahu bahwa situsnya ada di `web/`:

1. Vercel > proyek > **Settings** > **Build and Deployment** > **Root Directory** > Edit > isi `web` > Save.
2. Di bagian **Framework Settings**, pilih Framework Preset **Other**. Kosongkan Build Command dan Output Directory.
3. Deployments > titik tiga pada deploy terakhir > **Redeploy**.

Tanpa itu, Vercel melihat `requirements.txt` di akar dan mengira ini aplikasi Python (galat `PYTHON_ENTRYPOINT_NOT_FOUND`).
Preset framework yang tersimpan di proyek (ikon Python di dasbor) tidak berubah hanya karena menambah folder, jadi `web/vercel.json` dan
`vercel.json` di akar sama-sama berisi `"framework": null` (= preset Other) untuk menimpanya per-deploy.

Jika galat yang sama muncul lagi, cara paling bersih: hapus proyek Vercel lama, lalu Add New > Project > impor repo ini, klik Edit pada
**Root Directory** isi `web`, Framework Preset **Other**, lalu Deploy.

Setelah menambah atau mengubah style: `python -m pipeline.preview` lalu `python -m pipeline.bangun_web`, commit, push.
Uji halaman: `python tests/uji_halaman.py` (butuh `pip install playwright` dan `playwright install chromium`) dan `python tests/uji_web.py` (butuh node).

## Akun dan persetujuan admin (Supabase)

Login memakai Supabase Auth; tiap pengguna punya akun sendiri. Akun baru berstatus `menunggu`; admin mengaktifkannya
(dengan masa aktif) setelah langganan terkonfirmasi. Halaman: `masuk.html` (masuk, daftar, lupa dan atur ulang kata sandi,
status akun) dan `admin.html` (daftar pengguna, aktifkan atau perpanjang 30/90/365 hari, tangguhkan, log perubahan).
Tanpa konfigurasi, situs berjalan seperti biasa tanpa login.

**Penyiapan (sekali):**

1. supabase.com > New project (pilih region terdekat, mis. Singapore). Simpan kata sandi database di tempat aman.
2. **SQL Editor** > tempel seluruh `supabase/schema.sql` > Run.
3. **Authentication > Sign In / Providers**: pastikan Email aktif; sebaiknya biarkan "Confirm email" menyala dan atur panjang kata sandi minimal 8.
4. **Authentication > URL Configuration**: Site URL = alamat situs Vercel-mu; tambahkan `https://ALAMAT-KAMU/masuk.html` ke Redirect URLs
   (dipakai tautan konfirmasi dan pemulihan kata sandi).
5. **Project Settings > API**: salin Project URL dan kunci publik (publishable atau anon) ke `web/konfigurasi.js`. **Jangan** memakai kunci `secret`/`service_role`.
6. Daftar lewat `masuk.html` memakai emailmu, lalu jadikan dirimu admin di SQL Editor:
   `update public.profil set peran='admin', status='aktif', aktif_sampai=null where email='emailkamu@contoh.com';`
7. Jalankan `supabase/uji_rls.sql` sekali di SQL Editor: harus muncul NOTICE `SEMUA UJI LOLOS`. Skrip ini menguji aturan akses nyata
   (user biasa tidak bisa mengaktifkan dirinya, mengubah peran, atau membaca audit; admin tidak bisa mengubah akunnya sendiri, dll.) dan di-ROLLBACK.
8. Commit dan push `web/konfigurasi.js`.

**Catatan keamanan:**

- Kunci publik memang terlihat di browser. Yang melindungi data adalah Row Level Security di `schema.sql`; setiap tabel baru di schema `public` wajib mengaktifkannya.
- Peran (`peran`) hanya bisa diubah lewat SQL Editor, tidak lewat API. Admin tidak bisa mengubah akunnya sendiri (mencegah terkunci).
- Menggerbang halaman statis hanyalah kenyamanan: isi `web/` tetap bisa diunduh siapa pun. Perlindungan nyata datang saat ada layanan di server
  (job render, penyimpanan kunci API user) yang memakai `public.akses_aktif()` pada kebijakan tabelnya.
- Header keamanan (CSP, dsb.) dihasilkan `pipeline/bangun_web.py`. Jika memakai domain kustom untuk Supabase, tambahkan ke `connect-src` di berkas itu lalu jalankan ulang `python -m pipeline.bangun_web`.
- Pustaka `supabase-js` dimuat dari CDN dengan versi dipatok (lihat `web/auth.js`). Untuk pengamanan tambahan, unduh berkasnya ke `web/` dan muat dari sana.
- Paket gratis Supabase menjeda proyek yang tidak aktif seminggu; untuk layanan yang dipakai orang lain, pakai paket berbayar.
- Uji: `python tests/uji_auth.py` (stub Supabase; tidak menguji library asli), `node tests/uji_akses.js`.

## Mode server: video dirender di server (tanpa instal apa pun bagi pengguna)

Dengan akun aktif, pengguna cukup menyusun naskah lalu klik **Buat video**. Kunci API Gemini mereka disimpan terenkripsi
(Supabase Vault) lewat halaman **Pengaturan**; gambar diunggah ke penyimpanan privat; video muncul di **Video saya**
lengkap dengan kemajuan, unduhan, dan lembar kontak. Rendernya dikerjakan **worker** (lihat `worker/README.md`).

**Penyiapan tambahan di Supabase** (setelah `schema.sql`):

1. SQL Editor > tempel dan jalankan `supabase/job.sql` (tabel job, kunci terenkripsi, bucket `unggahan` dan `hasil`, aturan akses).
2. Jalankan `supabase/uji_job.sql`: harus muncul NOTICE `SEMUA UJI LOLOS`.
3. Project Settings > API: salin kunci **secret** untuk worker (JANGAN ke `web/konfigurasi.js`).
4. Jalankan worker (`worker/README.md`): komputermu sendiri untuk uji, atau VPS.

Alur: browser membuat baris di tabel `job` (hanya bisa atas nama sendiri dan hanya bila akun aktif) -> worker mengambilnya,
membaca kunci pemiliknya lewat fungsi khusus, memproses, mengunggah ke bucket `hasil` -> browser mengunduh lewat tautan bertanda tangan 10 menit.

| Bagian | Status |
|--------|--------|
| Worker (validasi, antrian, unggah, pembersihan), diuji dengan Supabase dan Gemini palsu | Teruji (27 uji termasuk serangan keamanan) |
| Halaman Pengaturan, Video saya, tombol Buat video, unggah gambar | Teruji di browser dengan stub Supabase (34 uji) |
| `job.sql`: antrian, Vault, bucket, aturan akses | Ditulis, **belum dijalankan**; jalankan `uji_job.sql` |
| Koneksi ke Supabase dan Gemini sungguhan, image Docker | **Belum teruji** |

Uji: `python tests/uji_worker.py`, `python tests/uji_server.py`.

## Mode lokal: menjalankan di komputer sendiri (Windows, macOS, Linux)

Tidak butuh bash; yang dibutuhkan hanya Python 3.10+ dan ffmpeg di PATH.
Windows: `winget install Gyan.FFmpeg`, lalu di PowerShell:

```powershell
py -m pip install -r requirements.txt
$env:GEMINI_API_KEY = "kunci-kamu"
py -m pipeline.otomatis --naskah naskah.json --out hasil\video.mp4
```

Catatan: GitHub Actions sengaja tidak dipakai untuk merender. Ketentuan GitHub membatasi pemakaiannya untuk
proyek perangkat lunak (bukan komputasi serverless atau layanan), jadi render dijalankan di komputermu atau server milikmu.

## Aturan yang dijaga kode

- Durasi video = durasi VO + ekor. VO tidak dipotong atau dipercepat.
- Gambar yang tercantum di `gambar_user` wajib dipakai di scene; kalau tidak, validasi gagal.
- Scene `angka` dan `bar` tanpa `sumber` memunculkan peringatan (`--ketat` menjadikannya galat). Sumber ditampilkan kecil di layar, kecuali bernilai `DATA CONTOH`.
- Cek otomatis: 30 fps, H.264, yuv420p, ada audio, selisih audio-video < 0,1 s, VO tidak terpotong, tidak ada frame hitam.

## Format timeline

```json
{
  "style": "bersih-edukasi",
  "gambar_user": ["aset/foto.jpg"],
  "scene": [ { "tipe": "hook", "mulai": 0.0, "selesai": 2.8, "teks": ["Baris satu", "Baris *dua*"] } ],
  "subtitle": [ { "mulai": 0.3, "selesai": 2.6, "teks": "Kalimat subtitle", "kata_kunci": ["subtitle"] } ]
}
```

Tanda `*kata*` menyorot kata dengan warna aksen. Field tingkat atas `akun` (mis. `"@akunkamu"`) menampilkan lencana nama akun milikmu di kiri atas. Waktu dalam detik; bagian isi scene dibuat dari timestamps VO.

| tipe | field wajib | opsional |
|------|-------------|----------|
| `hook` | `teks` (daftar baris) | |
| `angka` | `nilai`, `label` | `awalan`, `akhiran`, `desimal`, `sumber` |
| `poin` | `poin` (daftar) | `judul`, `waktu` (detik per poin) |
| `gambar` | `file` | `teks`, `mode` (auto/cover/contain), `bingkai` (kartu/penuh) |
| `bar` | `data` (1 sampai 6: `label`, `nilai`) | `judul`, `satuan`, `desimal`, `sumber` |
| `penutup` | `teks` (daftar baris) | `ajakan` |
| `label` | `teks` (string) | label bergaya stempel mandiri; atau isi `label` di dalam scene `hook` |

## Style: tentukan di awal, pilih saat dipakai

Setiap style = satu folder `styles/<id>/` berisi `style.json`, `preview.png`, dan `reference/` (gambar referensi).
Galeri untuk web app dibaca dari `pipeline.gaya.daftar()` (mengembalikan id, nama, deskripsi, **kategori**, preview).

| Keluarga | Style | Asal |
|----------|-------|------|
| **2D flat motion** | `panggung-sorot` (panggung gelap, lampu sorot, label merah) | referensi 1 |
| | `kartun-hangat` (krem halftone, subtitle stiker) | referensi 2 |
| | `kota-datar` (gedung datar berparalaks, jalan bergerak) | referensi 3 |
| | `bersih-edukasi`, `bold-neon`, `minimal-serif` | bawaan awal |
| **Pixel art** | `piksel-malam` (16 warna, dithering, garis scan CRT, langit malam) | rancangan baru |
| | `piksel-hijau` (5 warna ala konsol genggam, piksel besar) | rancangan baru |
| **3D motion** | `neon-3d` (lantai grid perspektif, matahari retro) | rancangan baru |
| | `studio-3d` (studio terang, huruf koral bertebal 3D) | rancangan baru |

Kemampuan yang bisa diatur per style di `style.json` (lihat `styles/_template/style.json`):

- Latar bergerak: `glow`, `solid`, `grid`, `sorot`, `kota`, `lantai3d`, `bintang`; pola overlay `titik` atau `garis`; palet latar sendiri lewat `latar_gerak.palet`.
- Teks: outline tebal (`judul_stroke`), huruf kapital, tebal 3D (`teks_3d`), subtitle dengan pil atau outline (`subtitle`).
- Elemen: label bergaya stempel (`label`), lencana akun, kartu poin miring 3D (`kartu_3d`), kolom grafik 3D (`bar_gaya: tiang3d`).
- Efek pasca-render (`efek`): `grain`, `vignette`, `scanline`, dan `piksel` (turunkan resolusi, batasi ke palet warna, dithering).
- `posisi_konten`: tinggi pusat konten (0 sampai 1) supaya tidak bertabrakan dengan latar yang tinggi.
- `gambar.gradasi`: matikan gradasi gelap saat gambar penuh dipakai sebagai latar ilustrasi.

Menambah style baru:

1. Salin `styles/_template/` menjadi `styles/<id-baru>/` dan ganti nilai bertanda `|` dengan satu nilai valid.
2. Taruh gambar referensi di `reference/`.
3. `python3 -m pipeline.ekstrak_palet styles/<id>/reference/*.png` menampilkan warna dominan **dan warna beraksen** (piksel jenuh, untuk elemen kecil seperti label merah). Itu saran awal; periksa visual.
4. Isi `style.json`: font, ukuran, gerak, latar, dan efek dinilai dari referensi (bisa dibantu Claude di chat dengan melampirkan gambarnya).
5. `python3 -m pipeline.preview <id-baru>`, lihat `preview.png`, sesuaikan sampai cocok.

### Batasan yang perlu diketahui

- **Karakter dan ilustrasi tidak digambar oleh kode.** Gaya kartun pada referensi (karakter, toko, sepeda) dibuat oleh ilustrator atau AI gambar. Mesin ini meniru *tampilan dan suasananya*: warna, tipografi, label, latar, efek, dan gerak. Ilustrasi karakter sendiri berasal dari gambar yang kamu berikan (`gambar` scene, mode penuh); mesin menambahkan subtitle, label, lencana akun, Ken Burns, dan efek style di atasnya. Tanpa gambar, scene memakai grafis dari kode.
- **Referensi bukan untuk disalin.** Nama kanal, karakter, dan logo pada gambar referensi milik pembuatnya. Hanya gaya umum (palet, tipografi, tata letak) yang dipakai; jangan memakai ulang merek atau karakter mereka.
- **Pixel art** dihasilkan filter pasca-render (resolusi rendah, palet terbatas, dithering) di atas font biasa, bukan font bitmap asli. Ilustrasi yang dimasukkan ke style pixel ikut berubah warna ke palet.
- **3D** adalah 3D perangkat lunak sederhana: ketebalan huruf, perspektif kartu, kolom isometrik, dan lantai grid. Bukan mesin 3D; tidak ada model 3D, pencahayaan fisik, atau kamera bebas.
- Kecepatan render sekitar 7 sampai 9 frame per detik di lingkungan uji: video 45 detik kira-kira 3 sampai 4 menit.

## Struktur

```
pipeline/   animasi, gaya, teks, scene, render, validasi, qc, buat_video, jalankan, preview, ekstrak_palet,
            tts_gemini, tts_tiruan, selaras, susun, naskah_gemini, buat_naskah, otomatis, rakit, bangun_web
styles/     10 style (2d-flat, pixelart, 3d), _template
assets/     fonts
examples/   timeline.contoh.json, naskah.contoh.json (data tiruan, bukan fakta)
tests/      uji_dasar.py, uji_lanjutan.py, uji_web.py, uji_halaman.py, uji_auth.py, uji_server.py, uji_worker.py, uji_akses.js, stub_supabase.js, timeline.gambar.json, aset/
web/        index.html, masuk.html, admin.html, app.css, app.js, naskah.js, akses.js, auth.js, konfigurasi.js, styles.json, previews/, fonts/
supabase/   schema.sql, job.sql (tabel, trigger, RLS, Vault, Storage), uji_rls.sql, uji_job.sql
worker/     main.py, proses.py, rest.py, Dockerfile, README.md (worker server)
```

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
| Workflow GitHub Actions (`buat-video.yml`) | YAML valid; **belum dijalankan di GitHub** |
| Web app Vercel | Belum dibuat |

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

## GitHub Actions

1. Push repo ini ke GitHub (**privat**), tambahkan secret `GEMINI_API_KEY` (Settings > Secrets and variables > Actions).
2. Opsional: variabel `GEMINI_TTS_MODEL`.
3. Actions > "Buat video" > Run workflow, tempel isi `naskah.json`. Hasil ada di Artifacts (disimpan 1 hari; unduh lalu biarkan terhapus sendiri).
4. Gambar dari user: commit ke `aset/` dan tulis path-nya di naskah.

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
pipeline/   animasi, gaya, teks, scene, render, validasi, qc, buat_video, preview, ekstrak_palet,
            tts_gemini, tts_tiruan, selaras, susun, naskah_gemini, buat_naskah, otomatis
styles/     10 style (2d-flat, pixelart, 3d), _template
assets/     fonts
scripts/    rakit_mp4.sh (video + VO + musik opsional, ducking, cek teknis)
examples/   timeline.contoh.json, naskah.contoh.json (data tiruan, bukan fakta)
tests/      uji_dasar.py, uji_lanjutan.py, timeline.gambar.json, aset/
.github/    workflows/buat-video.yml
```

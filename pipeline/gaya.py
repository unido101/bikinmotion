"""Memuat dan memvalidasi style. Style = satu folder styles/<id>/ berisi style.json."""
import copy
import json
from pathlib import Path

from PIL import ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "assets" / "fonts"
STYLE_DIR = ROOT / "styles"

DEFAULT = {
    "id": "tanpa-nama",
    "nama": "Tanpa nama",
    "deskripsi": "",
    "kategori": "2d-flat",
    "posisi_konten": 0.42,
    "canvas": {"w": 1080, "h": 1920, "fps": 30},
    "warna": {
        "latar": "#0E111C", "latar2": "#161B2E", "teks": "#F5F7FC",
        "aksen": "#FFC43D", "aksen2": "#5AD1FF", "redup": "#9AA3B8",
        "kartu": "#1B2138", "teks_di_aksen": "#0E111C",
        "label": "#D14E41", "teks_label": "#FFFFFF", "stroke": "#000000",
    },
    "font": {"judul": "Poppins-Bold.ttf", "isi": "Poppins-Medium.ttf", "subtitle": "Poppins-Bold.ttf"},
    "ukuran": {"hook": 118, "angka": 280, "isi": 68, "label": 64, "subtitle": 56, "kecil": 44},
    "huruf_besar_judul": False,
    "latar_gerak": {"tipe": "glow", "kekuatan": 0.22, "pola": "", "palet": {}},
    "judul_stroke": 0,
    "teks_3d": {"aktif": False, "kedalaman": 0, "arah": [1, 1], "warna_sisi": "#000000", "gelap": 0.45},
    "kartu_3d": {"aktif": False, "sudut": 14},
    "bar_gaya": "datar",
    "gambar": {"gradasi": True},
    "akun": {"gaya": "pil"},
    "efek": {"grain": 0.0, "vignette": 0.0, "scanline": 0.0,
             "piksel": {"skala": 0, "palet": [], "dither": 0.0}},
    "gerak": {"masuk": 0.45, "easing": "ease_out", "stagger": 0.14, "hitung": 1.3, "zoom_gambar": 0.07},
    "transisi": {"tipe": "naik", "masuk": 0.35, "keluar": 0.25},
    "subtitle": {"aktif": True, "y": 0.80, "latar": "pill", "lebar": 940, "stroke": 4, "huruf_besar": False, "alpha_pill": 0.66},
    "bentuk": {"radius": 36},
    "progress_bar": True,
    "safe_zone": {"atas": 150, "bawah": 250, "sisi": 60},
}


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _gabung(dasar, atas):
    hasil = copy.deepcopy(dasar)
    for k, v in atas.items():
        if isinstance(v, dict) and isinstance(hasil.get(k), dict):
            hasil[k] = _gabung(hasil[k], v)
        else:
            hasil[k] = v
    return hasil


class Gaya:
    def __init__(self, data, folder=None):
        self.data = _gabung(DEFAULT, data)
        self.folder = folder
        d = self.data
        self.id = d["id"]
        self.nama = d["nama"]
        self.W, self.H, self.fps = d["canvas"]["w"], d["canvas"]["h"], d["canvas"]["fps"]
        self.warna = {k: hex_rgb(v) for k, v in d["warna"].items()}
        self.ukuran = d["ukuran"]
        self.gerak = d["gerak"]
        self.transisi = d["transisi"]
        self.subtitle = d["subtitle"]
        self.latar_gerak = d["latar_gerak"]
        self.radius = d["bentuk"]["radius"]
        self.safe = d["safe_zone"]
        self.huruf_besar = d["huruf_besar_judul"]
        self.progress_bar = d["progress_bar"]
        self.kategori = d["kategori"]
        self.posisi_konten = d["posisi_konten"]
        self.judul_stroke = d["judul_stroke"]
        self.warna_stroke = self.warna.get("stroke", (0, 0, 0))
        t3 = d["teks_3d"]
        self.extrude = None
        if t3.get("aktif") and t3.get("kedalaman", 0) > 0:
            self.extrude = {"kedalaman": t3["kedalaman"], "arah": tuple(t3["arah"]),
                            "sisi": hex_rgb(t3["warna_sisi"]), "gelap": t3["gelap"]}
        self.kartu3d = d["kartu_3d"]
        self.bar_gaya = d["bar_gaya"]
        self.gambar_opsi = d["gambar"]
        self.akun = d["akun"]
        self.efek = d["efek"]
        self._font = {}

    def font(self, peran, ukuran):
        """peran: judul | isi | subtitle. Hasilnya di-cache per (berkas, ukuran)."""
        berkas = self.data["font"][peran]
        kunci = (berkas, int(ukuran))
        if kunci not in self._font:
            self._font[kunci] = ImageFont.truetype(str(FONT_DIR / berkas), max(8, int(ukuran)))
        return self._font[kunci]

    def cek(self):
        """Daftar masalah style (kosong bila baik)."""
        masalah = []
        for peran, berkas in self.data["font"].items():
            if not (FONT_DIR / berkas).exists():
                masalah.append(f"font '{berkas}' (peran {peran}) tidak ada di assets/fonts")
        for k in ("latar", "teks", "aksen"):
            if k not in self.warna:
                masalah.append(f"warna '{k}' wajib ada")
        if self.W % 2 or self.H % 2:
            masalah.append("lebar dan tinggi kanvas harus genap (syarat yuv420p)")
        return masalah


def muat(id_atau_path):
    p = Path(id_atau_path)
    if not p.suffix:
        p = STYLE_DIR / id_atau_path / "style.json"
    if not p.exists():
        raise FileNotFoundError(f"style tidak ditemukan: {id_atau_path} (dicari di {p})")
    return Gaya(json.loads(p.read_text(encoding="utf-8")), folder=p.parent)


def daftar():
    """Semua style yang tersedia, untuk galeri pemilihan."""
    hasil = []
    for f in sorted(STYLE_DIR.glob("*/style.json")):
        if f.parent.name.startswith("_"):
            continue  # _template bukan style yang bisa dipilih
        d = json.loads(f.read_text(encoding="utf-8"))
        hasil.append({
            "id": d.get("id", f.parent.name),
            "nama": d.get("nama", f.parent.name),
            "deskripsi": d.get("deskripsi", ""),
            "kategori": d.get("kategori", "2d-flat"),
            "preview": str((f.parent / "preview.png").relative_to(ROOT)) if (f.parent / "preview.png").exists() else None,
        })
    return hasil

"""Renderer: frame(t) murni dari waktu. Frame dialirkan ke ffmpeg lewat stdin.

Urutan per frame: latar (bergerak) -> scene aktif -> subtitle -> lencana akun -> progress bar -> efek pasca-render.
"""
import math
import random
import subprocess
import sys

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .animasi import clamp, ease_in, ease_out, prog
from .gaya import hex_rgb
from .scene import SCENE, Ctx, lencana_akun, subtitle


# ------------------------------------------------------------------ utilitas
def _gradien(W, H, atas, bawah):
    a, b = np.array(atas, float), np.array(bawah, float)
    t = np.linspace(0, 1, H)[:, None, None]
    arr = (a * (1 - t) + b * t).astype(np.uint8)
    return Image.fromarray(np.repeat(arr, W, axis=1), "RGB")


def _glow(warna, ukuran, kekuatan):
    ax = np.linspace(-1, 1, ukuran)
    xx, yy = np.meshgrid(ax, ax)
    alpha = (np.exp(-((xx ** 2 + yy ** 2) / 0.28)) * 255 * kekuatan).astype(np.uint8)
    return Image.new("RGB", (ukuran, ukuran), tuple(warna)), Image.fromarray(alpha, "L")


def _campur(a, b, f):
    return tuple(int(a[i] * (1 - f) + b[i] * f) for i in range(3))


def _pal(g, bawaan):
    """Palet latar: bawaan style (latar_gerak.palet, hex) menimpa bawaan kode."""
    p = dict(bawaan)
    p.update(g.latar_gerak.get("palet", {}))
    return {k: hex_rgb(v) for k, v in p.items()}


# ------------------------------------------------------------------ latar
class Latar:
    def __init__(self, g):
        self.g = g
        self.tipe = g.latar_gerak["tipe"]
        init = getattr(self, f"_init_{self.tipe}", None)
        if init is None:
            raise ValueError(f"tipe latar tidak dikenal: {self.tipe}")
        init()
        self.pola = self._buat_pola(g.latar_gerak.get("pola", ""))

    def frame(self, t):
        img = getattr(self, f"_frame_{self.tipe}")(t)
        if self.pola is not None:
            img.paste(self.pola[0], (0, 0), self.pola[1])
        return img

    # ---- pola overlay statis
    def _buat_pola(self, nama):
        g = self.g
        if not nama:
            return None
        warna = _campur(g.warna["latar"], g.warna["teks"], 0.10)
        m = Image.new("L", (g.W, g.H), 0)
        d = ImageDraw.Draw(m)
        if nama == "titik":
            sp = 46
            for y in range(sp // 2, g.H, sp):
                for x in range(sp // 2 + (sp // 2 if (y // sp) % 2 else 0), g.W, sp):
                    d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=255)
        elif nama == "garis":
            for y in range(0, g.H, 24):
                d.line([(0, y), (g.W, y)], fill=255, width=2)
        return Image.new("RGB", (g.W, g.H), warna), m.point(lambda v: int(v * 0.55))

    # ---- solid
    def _init_solid(self):
        self.base = Image.new("RGB", (self.g.W, self.g.H), self.g.warna["latar"])

    def _frame_solid(self, t):
        return self.base.copy()

    # ---- glow (dua cahaya lembut yang melayang)
    def _init_glow(self):
        g = self.g
        self.base = _gradien(g.W, g.H, g.warna["latar"], g.warna.get("latar2", g.warna["latar"]))
        k = g.latar_gerak["kekuatan"]
        self.glow1 = _glow(g.warna["aksen"], 1200, k)
        self.glow2 = _glow(g.warna.get("aksen2", g.warna["aksen"]), 1200, k * 0.8)

    def _frame_glow(self, t):
        g = self.g
        img = self.base.copy()
        x1 = g.W * 0.15 + math.sin(t * 0.35) * 160 - 600
        y1 = g.H * 0.12 + math.cos(t * 0.27) * 140 - 600
        x2 = g.W * 0.9 + math.cos(t * 0.30) * 150 - 600
        y2 = g.H * 0.85 + math.sin(t * 0.33) * 150 - 600
        img.paste(self.glow1[0], (int(x1), int(y1)), self.glow1[1])
        img.paste(self.glow2[0], (int(x2), int(y2)), self.glow2[1])
        return img

    # ---- grid
    def _init_grid(self):
        g = self.g
        self.base = _gradien(g.W, g.H, g.warna["latar"], g.warna.get("latar2", g.warna["latar"]))
        self.garis = _campur(g.warna["latar"], g.warna["teks"], 0.07)

    def _frame_grid(self, t):
        g = self.g
        img = self.base.copy()
        d, sp, off = ImageDraw.Draw(img), 90, (t * 18) % 90
        for x in range(0, g.W + sp, sp):
            d.line([(x, 0), (x, g.H)], fill=self.garis, width=2)
        for y in range(-sp, g.H + sp, sp):
            d.line([(0, y + off), (g.W, y + off)], fill=self.garis, width=2)
        return img

    # ---- sorot: panggung gelap dengan lampu sorot, lantai kayu, debu melayang
    def _init_sorot(self):
        g, W, H = self.g, self.g.W, self.g.H
        p = _pal(g, {"atas": "#2B190E", "bawah": "#0E0806", "samping": "#8A4A16", "lantai": "#3B2314",
                     "garis": "#24150B", "cahaya": "#FFE9B8"})
        self.pal = p
        yl = int(H * 0.70)
        self.yl = yl
        base = _gradien(W, H, p["atas"], p["bawah"])
        xs = np.linspace(0, 1, W)[None, :]
        ys = np.linspace(0, 1, H)[:, None]
        sisi = np.maximum(np.exp(-((xs - 0.0) / 0.13) ** 2), np.exp(-((xs - 1.0) / 0.13) ** 2)) * (1 - 0.5 * ys)
        base.paste(Image.new("RGB", (W, H), p["samping"]), (0, 0), Image.fromarray((sisi * 150).astype(np.uint8), "L"))
        d = ImageDraw.Draw(base)
        d.rectangle([0, yl, W, H], fill=p["lantai"])
        for i in range(1, 11):
            y = int(yl + (H - yl) * (i / 10) ** 1.7)
            d.line([(0, y), (W, y)], fill=p["garis"], width=3)
        for k in range(-8, 9):
            d.line([(W / 2 + k * 40, yl), (W / 2 + k * 190, H)], fill=p["garis"], width=3)
        kolam = Image.new("L", (W, H), 0)
        ImageDraw.Draw(kolam).ellipse([W * 0.16, yl + 30, W * 0.84, yl + 330], fill=210)
        kolam = kolam.filter(ImageFilter.GaussianBlur(46))
        base.paste(Image.new("RGB", (W, H), p["cahaya"]), (0, 0), kolam.point(lambda v: int(v * 0.55)))
        d = ImageDraw.Draw(base)
        d.ellipse([W / 2 - 52, 96, W / 2 + 52, 150], fill=(26, 18, 14))
        self.base = base
        kerucut = Image.new("L", (W, H), 0)
        ImageDraw.Draw(kerucut).polygon([(W / 2 - 44, 138), (W / 2 + 44, 138), (W / 2 + 430, yl + 150), (W / 2 - 430, yl + 150)], fill=255)
        kerucut = kerucut.filter(ImageFilter.GaussianBlur(30))
        grad = np.clip(1 - (np.arange(H) - 138) / max(1, (yl + 150 - 138)), 0, 1) ** 0.9 * 0.62 + 0.04
        self.kerucut = Image.fromarray((np.array(kerucut) * grad[:, None]).astype(np.uint8), "L")
        self.warna_cahaya = Image.new("RGB", (W, H), p["cahaya"])
        rnd = random.Random(7)
        self.debu = [(rnd.uniform(W * 0.28, W * 0.72), rnd.uniform(160, yl + 100), rnd.uniform(8, 20),
                      rnd.uniform(2.5, 5.5), rnd.uniform(0, 6.28)) for _ in range(48)]

    def _frame_sorot(self, t):
        g = self.g
        img = self.base.copy()
        kedip = 0.93 + 0.07 * math.sin(t * 5.3) * math.sin(t * 1.7)
        ayun = int(math.sin(t * 0.6) * 12)
        img.paste(self.warna_cahaya, (ayun, 0), self.kerucut.point(lambda v: int(v * kedip)))
        d = ImageDraw.Draw(img)
        rentang = self.yl + 100 - 160
        for x0, y0, v, r, ph in self.debu:
            y = 160 + (y0 - 160 - v * t) % rentang
            x = x0 + math.sin(t * 0.8 + ph) * 22 + ayun
            tw = 0.45 + 0.55 * abs(math.sin(t * 1.6 + ph))
            warna = _campur((60, 50, 40), (255, 240, 205), tw)
            d.ellipse([x - r, y - r, x + r, y + r], fill=warna)
        return img

    # ---- kota: langit, gedung datar berparalaks, semak, trotoar, jalan dengan marka bergerak
    def _init_kota(self):
        g, W, H = self.g, self.g.W, self.g.H
        p = _pal(g, {"langit_atas": "#4A98B8", "langit_bawah": "#BCD6CF", "gedung1": "#7F8FB5", "gedung2": "#B7BED0",
                     "gedung3": "#E3D5A1", "jendela": "#5E6D93", "garis": "#1F2A3A", "semak": "#2E9E56",
                     "semak_gelap": "#1C7B45", "trotoar": "#A7AFAA", "aspal": "#667686", "marka": "#E3E5DB"})
        self.pal = p
        self.y_gedung = int(H * 0.70)
        self.y_semak = int(H * 0.805)
        self.y_trotoar = int(H * 0.83)
        base = _gradien(W, H, p["langit_atas"], p["langit_bawah"])
        d = ImageDraw.Draw(base)
        d.rectangle([0, self.y_trotoar, W, self.y_trotoar + 70], fill=p["trotoar"])
        d.rectangle([0, self.y_trotoar + 70, W, H], fill=p["aspal"])
        d.line([(0, self.y_trotoar + 70), (W, self.y_trotoar + 70)], fill=p["garis"], width=4)
        self.base = base
        rnd = random.Random(11)
        tinggi_tile = 760
        sky = Image.new("RGBA", (2 * W, tinggi_tile), (0, 0, 0, 0))
        ds = ImageDraw.Draw(sky)
        x = 0
        while x < W:
            bw = rnd.randint(130, 270)
            bw = min(bw, W - x) if W - x < 300 else bw
            bh = rnd.randint(260, 430)
            warna = rnd.choice([p["gedung1"], p["gedung2"], p["gedung3"]])
            for ox in (x, x + W):
                ds.rectangle([ox, tinggi_tile - bh, ox + bw, tinggi_tile], fill=warna, outline=p["garis"], width=4)
                for wy in range(tinggi_tile - bh + 36, tinggi_tile - 30, 62):
                    for wx in range(ox + 24, ox + bw - 34, 46):
                        ds.rectangle([wx, wy, wx + 24, wy + 34], fill=p["jendela"])
            x += bw + rnd.randint(-10, 18)
        self.sky_tile = sky
        semak = Image.new("RGBA", (2 * W, 260), (0, 0, 0, 0))
        dm = ImageDraw.Draw(semak)
        x = -40
        while x < W + 60:
            r = rnd.randint(62, 110)
            for ox in (x, x + W):
                dm.ellipse([ox - r, 260 - 2 * r + 20, ox + r, 260 + 20], fill=p["semak"], outline=p["garis"], width=3)
                dm.ellipse([ox - r * 0.55, 260 - 2 * r + 46, ox + r * 0.1, 260 - r * 0.9], fill=p["semak_gelap"])
            x += rnd.randint(70, 130)
        dm.rectangle([0, 238, 2 * W, 260], fill=p["semak_gelap"])
        self.semak_tile = semak

    def _frame_kota(self, t):
        g, W = self.g, self.g.W
        img = self.base.copy()
        o1 = int((14 * t) % W)
        img.paste(self.sky_tile, (-o1, self.y_gedung - 760), self.sky_tile)
        o2 = int((46 * t) % W)
        img.paste(self.semak_tile, (-o2, self.y_semak - 240), self.semak_tile)
        d = ImageDraw.Draw(img)
        d.rectangle([0, self.y_semak + 14, W, self.y_trotoar], fill=self.pal["semak_gelap"])
        d.rectangle([0, self.y_trotoar - 2, W, self.y_trotoar + 4], fill=self.pal["garis"])
        yg = int(g.H * 0.93)
        off = (260 * t) % 240
        for x in range(-240, W + 240, 240):
            d.rectangle([x + off, yg, x + off + 130, yg + 14], fill=self.pal["marka"])
        return img

    # ---- lantai3d: matahari retro, cakrawala, grid perspektif yang bergulir
    def _init_lantai3d(self):
        g, W, H = self.g, self.g.W, self.g.H
        p = _pal(g, {"langit_atas": "#10002B", "langit_bawah": "#6A1B80", "matahari_atas": "#FFD166",
                     "matahari_bawah": "#FF2E93", "lantai_atas": "#14012E", "lantai_bawah": "#2B0A45",
                     "grid": "#FF2E93", "grid2": "#2EF2FF"})
        self.pal = p
        hz = int(H * 0.52)
        self.hz = hz
        base = _gradien(W, H, p["langit_atas"], p["langit_bawah"])
        d = ImageDraw.Draw(base)
        cx, cy, r = W // 2, hz - 40, 330
        for y in range(cy - r, hz):
            f = (y - (cy - r)) / (2 * r)
            half = math.sqrt(max(0, r * r - (y - cy) ** 2))
            d.line([(cx - half, y), (cx + half, y)], fill=_campur(p["matahari_atas"], p["matahari_bawah"], clamp(f)))
        celah = 6
        yy = cy + 20
        while yy < hz:
            f = (yy - cy) / r
            d.rectangle([0, yy, W, yy + celah * (1 + 2 * f)], fill=_campur(p["langit_atas"], p["langit_bawah"], hz and yy / hz))
            yy += 34
        lantai = _gradien(W, H - hz, p["lantai_atas"], p["lantai_bawah"])
        base.paste(lantai, (0, hz))
        d = ImageDraw.Draw(base)
        d.line([(0, hz), (W, hz)], fill=p["grid2"], width=4)
        glow = Image.new("L", (W, H), 0)
        dg = ImageDraw.Draw(glow)
        for k in range(-16, 17):
            titik = [(W / 2, hz), (W / 2 + k * 170, H)]
            dg.line(titik, fill=255, width=9)
            d.line(titik, fill=p["grid"], width=3)
        glow = glow.filter(ImageFilter.GaussianBlur(9))
        base.paste(Image.new("RGB", (W, H), p["grid"]), (0, 0), glow.point(lambda v: int(v * 0.5)))
        self.base = base
        rnd = random.Random(5)
        self.bintang = [(rnd.uniform(0, W), rnd.uniform(0, hz - 60), rnd.uniform(1, 3.2), rnd.uniform(0, 6.28)) for _ in range(110)]

    def _frame_lantai3d(self, t):
        g, W, H, hz = self.g, self.g.W, self.g.H, self.hz
        img = self.base.copy()
        d = ImageDraw.Draw(img)
        for x, y, r, ph in self.bintang:
            tw = 0.3 + 0.7 * abs(math.sin(t * 1.4 + ph))
            d.ellipse([x - r, y - r, x + r, y + r], fill=_campur(self.pal["langit_atas"], (255, 255, 255), tw))
        n = 18
        geser = (t * 0.55) % 1.0
        for i in range(n):
            z = ((i + geser) / n)
            y = hz + (H - hz) * z ** 2.3
            w = 2 + int(5 * z)
            warna = _campur(self.pal["lantai_atas"], self.pal["grid2"], 0.25 + 0.75 * z)
            d.line([(0, y), (W, y)], fill=warna, width=w)
        return img

    # ---- bintang: langit malam piksel dengan bintang berkedip dan siluet kota (cocok dengan efek piksel)
    def _init_bintang(self):
        g, W, H = self.g, self.g.W, self.g.H
        p = _pal(g, {"atas": "#0B1026", "bawah": "#2A2F6B", "siluet": "#0A0C1A", "jendela": "#FFD166", "bulan": "#F4F1DE"})
        self.pal = p
        base = _gradien(W, H, p["atas"], p["bawah"])
        d = ImageDraw.Draw(base)
        d.ellipse([W * 0.70, H * 0.08, W * 0.70 + 150, H * 0.08 + 150], fill=p["bulan"])
        rnd = random.Random(21)
        x = 0
        yb = int(H * 0.88)
        while x < W:
            bw, bh = rnd.randint(90, 200), rnd.randint(220, 560)
            d.rectangle([x, yb - bh, x + bw, H], fill=p["siluet"])
            for wy in range(yb - bh + 30, yb - 20, 54):
                for wx in range(x + 18, x + bw - 28, 40):
                    if rnd.random() < 0.38:
                        d.rectangle([wx, wy, wx + 20, wy + 28], fill=p["jendela"])
            x += bw + rnd.randint(0, 14)
        self.base = base
        rnd = random.Random(9)
        self.bintang = [(rnd.uniform(0, W), rnd.uniform(0, H * 0.7), rnd.choice([0, 1, 2]), rnd.uniform(0, 6.28)) for _ in range(120)]

    def _frame_bintang(self, t):
        g = self.g
        img = self.base.copy()
        d = ImageDraw.Draw(img)
        for x, y, lapis, ph in self.bintang:
            kec = 6 + 5 * lapis
            xx = (x - kec * t) % g.W
            if math.sin(t * 2.0 + ph) > -0.35:
                r = 2 + lapis
                d.rectangle([xx - r, y - r, xx + r, y + r], fill=(235, 235, 255))
        return img


# ------------------------------------------------------------------ efek pasca-render
BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], float) / 16.0 - 0.5


class Efek:
    def __init__(self, g):
        self.g = g
        e = g.efek
        W, H = g.W, g.H
        self.skala = int(e["piksel"].get("skala", 0))
        self.palet = np.array([hex_rgb(h) for h in e["piksel"].get("palet", [])], float)
        self.dither = float(e["piksel"].get("dither", 0.0))
        self.noise = []
        if e.get("grain", 0) > 0:
            rng = np.random.default_rng(3)
            for _ in range(4):
                n = np.clip(rng.normal(128, 255 * e["grain"] * 0.5, (H, W)), 0, 255).astype(np.uint8)
                self.noise.append(Image.merge("RGB", (Image.fromarray(n),) * 3))
        self.vignette = None
        if e.get("vignette", 0) > 0:
            xs = np.linspace(-1, 1, W)[None, :]
            ys = np.linspace(-1, 1, H)[:, None]
            r = np.sqrt(xs ** 2 * 0.8 + ys ** 2 * 0.6)
            m = np.clip((r - 0.55) / 0.75, 0, 1) ** 1.6 * 255 * e["vignette"]
            self.vignette = Image.fromarray(m.astype(np.uint8), "L")
        self.scan = None
        if e.get("scanline", 0) > 0:
            m = np.zeros((H, W), np.uint8)
            per = max(4, self.skala or 4)
            for y in range(0, H, per):
                m[y:y + max(1, per // 3)] = int(255 * e["scanline"])
            self.scan = Image.fromarray(m, "L")

    def _piksel(self, img):
        g, s = self.g, self.skala
        kecil = img.resize((g.W // s, g.H // s), Image.BOX)
        if len(self.palet):
            a = np.asarray(kecil, dtype=np.float32)
            if self.dither > 0:
                h, w = a.shape[:2]
                thr = np.tile(BAYER4, (h // 4 + 1, w // 4 + 1))[:h, :w]
                a = a + thr[:, :, None] * 255 * self.dither * 0.35
            idx = ((a[:, :, None, :] - self.palet[None, None, :, :]) ** 2).sum(-1).argmin(-1)
            kecil = Image.fromarray(self.palet[idx].astype(np.uint8), "RGB")
        return kecil.resize((g.W, g.H), Image.NEAREST)

    def terapkan(self, img, t):
        if self.skala > 1:
            img = self._piksel(img)
        if self.noise:
            img = ImageChops.add(img, self.noise[int(t * 12) % len(self.noise)], 1.0, -128)
        if self.vignette is not None:
            img.paste((0, 0, 0), (0, 0), self.vignette)
        if self.scan is not None:
            img.paste((0, 0, 0), (0, 0), self.scan)
        return img


# ------------------------------------------------------------------ renderer
class Renderer:
    def __init__(self, tl, g, durasi):
        self.tl, self.g, self.durasi = tl, g, durasi
        self.scene = sorted(tl["scene"], key=lambda s: s["mulai"])
        self.subs = tl.get("subtitle", [])
        self.akun = tl.get("akun", "")
        self.cy = g.H * (g.posisi_konten if self.subs and g.subtitle.get("aktif", True) else g.posisi_konten + 0.05)
        self.latar = Latar(g)
        self.efek = Efek(g)

    def frame(self, t):
        g = self.g
        img = self.latar.frame(t)
        for s in self.scene:
            if not (s["mulai"] <= t < s["selesai"]):
                continue
            lt, dur = t - s["mulai"], s["selesai"] - s["mulai"]
            tr = g.transisi
            masuk = ease_out(prog(lt, 0, tr["masuk"]))
            keluar = ease_in(prog(lt, dur - tr["keluar"], tr["keluar"])) if dur > tr["masuk"] + tr["keluar"] else 0.0
            a = masuk * (1 - keluar)
            geser = ((1 - masuk) * 70 - keluar * 50) if tr["tipe"] == "naik" else 0.0
            SCENE[s["tipe"]](Ctx(img, g, a, geser, self.cy), s, lt, dur)
        c = Ctx(img, g, 1.0, 0.0, self.cy)
        for item in self.subs:
            if item["mulai"] <= t < item["selesai"]:
                subtitle(c, item, t)
        lencana_akun(c, self.akun)
        if g.progress_bar:
            ImageDraw.Draw(img).rectangle([0, 0, int(g.W * clamp(t / self.durasi)), 8], fill=g.warna["aksen"])
        return self.efek.terapkan(img, t)


def render_video(tl, g, durasi, keluar, tampil_progres=True):
    """Render video bisu H.264 30 fps sepanjang `durasi` detik ke berkas `keluar`."""
    r = Renderer(tl, g, durasi)
    n = round(durasi * g.fps)
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{g.W}x{g.H}", "-r", str(g.fps), "-i", "-", "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", str(keluar)],
        stdin=subprocess.PIPE)
    try:
        for i in range(n):
            ff.stdin.write(r.frame(i / g.fps).tobytes())
            if tampil_progres and i % (g.fps * 2) == 0:
                print(f"  render {i}/{n} frame", file=sys.stderr, flush=True)
    finally:
        ff.stdin.close()
        ff.wait()
    if ff.returncode != 0:
        raise RuntimeError("ffmpeg gagal saat render")
    return n

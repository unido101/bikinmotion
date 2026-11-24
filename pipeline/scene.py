"""Pustaka scene. Setiap scene: fungsi(c, s, t, dur) yang menggambar ke c.img.

c   : Ctx (kanvas, style, alpha dan geser transisi, pusat vertikal konten)
s   : dict scene dari timeline
t   : waktu lokal scene (detik sejak scene mulai)
dur : durasi scene
"""
import math
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .animasi import ambil, clamp, ease_out, fmt_angka, overshoot, prog
from .teks import gambar_blok, kotak, lingkaran, miring_y, tata, tulis


class Ctx:
    def __init__(self, img, g, a=1.0, geser=0.0, cy=None):
        self.img, self.g, self.a, self.geser = img, g, a, geser
        self.cy = cy if cy is not None else g.H * 0.42

    @property
    def lebar(self):
        return self.g.W - 2 * self.g.safe["sisi"]


def _judul(g, teks):
    return teks.upper() if g.huruf_besar else teks


def _masuk(g, t, mulai):
    """(alpha, geser_y) untuk elemen yang masuk pada waktu `mulai`."""
    e = ambil(g.gerak["easing"])(prog(t, mulai, g.gerak["masuk"]))
    return clamp(e), (1 - e) * 55


def _st(g):
    """Opsi teks judul dari style: outline tebal dan ketebalan 3D."""
    return {"stroke": g.judul_stroke, "stroke_fill": g.warna_stroke, "extrude": g.extrude}


def _stempel(c, teks, yc, t, mulai):
    """Label bergaya stempel/spanduk: kotak berwarna dengan tepi putih, muncul membal dan sedikit miring."""
    g = c.g
    p = prog(t, mulai, 0.55)
    if p <= 0:
        return
    f = g.font("judul", g.ukuran["label"])
    baris, tt, th = tata(teks.upper(), f, c.lebar - 120, spasi=1.1)
    padx, pady, tepi = 46, 26, 8
    lebar_teks = max(sum(f.getlength(k) for k, _ in b) + f.getlength(" ") * (len(b) - 1) for b in baris)
    w, h = int(lebar_teks + 2 * padx + 2 * tepi), int(tt + 2 * pady + 2 * tepi)
    kotak_ = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(kotak_)
    r = max(6, g.radius // 3)
    d.rounded_rectangle([tepi, tepi, w - tepi - 1, h - tepi - 1], radius=r, fill=g.warna["label"])
    gambar_blok(kotak_, baris, th, w / 2, tepi + pady, f, g.warna["teks_label"], g.warna["teks_label"], 1.0,
                stroke=3, stroke_fill=(30, 12, 8))
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=r + tepi // 2, fill=255)
    rgba = kotak_.convert("RGBA")
    rgba.putalpha(m)
    skala = max(0.05, overshoot(p))
    sudut = -3.0 + math.sin(t * 7) * 1.4 * (1 - p)
    rgba = rgba.rotate(sudut, expand=True, resample=Image.BICUBIC)
    rgba = rgba.resize((max(1, int(rgba.width * skala)), max(1, int(rgba.height * skala))), Image.BICUBIC)
    mask = rgba.getchannel("A")
    a = clamp(p * 3) * c.a
    if a < 0.999:
        mask = mask.point(lambda v: int(v * a))
    c.img.paste(rgba.convert("RGB"), (int(g.W / 2 - rgba.width / 2), int(yc - rgba.height / 2 + c.geser)), mask)


# ---------------------------------------------------------------- hook
def hook(c, s, t, dur):
    g = c.g
    font = g.font("judul", g.ukuran["hook"])
    blok = []
    for baris in s["teks"]:
        b, tt, th = tata(_judul(g, baris), font, c.lebar, spasi=1.08)
        blok.append((b, tt, th))
    jarak = 26
    total = sum(x[1] for x in blok) + jarak * (len(blok) - 1)
    ada_label = bool(s.get("label"))
    y = c.cy - total / 2 - (60 if ada_label else 0)
    for i, (b, tt, th) in enumerate(blok):
        a, dy = _masuk(g, t, i * g.gerak["stagger"] * 2)
        gambar_blok(c.img, b, th, g.W / 2, y + dy + c.geser, font, g.warna["teks"], g.warna["aksen"], a * c.a, **_st(g))
        y += tt + jarak
    if ada_label:
        _stempel(c, s["label"], y + 70, t, 0.9)


# ---------------------------------------------------------------- angka
def angka(c, s, t, dur):
    g = c.g
    nilai, des = float(s["nilai"]), int(s.get("desimal", 0))
    awalan, akhiran = s.get("awalan", ""), s.get("akhiran", "")
    v = nilai * ease_out(prog(t, 0.15, g.gerak["hitung"]))
    teks = awalan + fmt_angka(v, des) + akhiran
    akhir = awalan + fmt_angka(nilai, des) + akhiran

    dasar = g.ukuran["angka"]
    lebar_akhir = g.font("judul", dasar).getlength(akhir)
    fit = min(1.0, c.lebar / max(1.0, lebar_akhir))
    skala = max(0.05, overshoot(prog(t, 0, 0.6)))
    font = g.font("judul", dasar * fit * min(skala, 1.12))
    a = clamp(prog(t, 0, 0.3)) * c.a
    tinggi = dasar * fit * 0.78
    y_angka = c.cy - 70 + c.geser
    tulis(c.img, teks, (g.W / 2, y_angka), font, g.warna["aksen"], a, anchor="mm", **_st(g))

    font_l = g.font("isi", g.ukuran["label"])
    b, tt, th = tata(s["label"], font_l, c.lebar)
    al, dl = _masuk(g, t, 0.55)
    y_label = y_angka + tinggi / 2 + 40 + dl
    gambar_blok(c.img, b, th, g.W / 2, y_label, font_l, g.warna["teks"], g.warna["aksen"], al * c.a,
                stroke=min(g.judul_stroke, 5), stroke_fill=g.warna_stroke)

    sumber = s.get("sumber", "")
    if sumber and s.get("tampilkan_sumber", True) and not sumber.upper().startswith("DATA CONTOH"):
        fk = g.font("isi", g.ukuran["kecil"])
        tulis(c.img, f"Sumber: {sumber}", (g.W / 2, y_label + tt + 50), fk, g.warna["redup"],
              clamp(prog(t, 0.9, 0.4)) * c.a, anchor="mt")


# ---------------------------------------------------------------- poin
def _kartu_poin(g, w, h, nomor, baris, th, tt, font):
    """Satu kartu poin sebagai gambar RGBA mandiri (agar bisa dimiringkan 3D)."""
    kartu = Image.new("RGB", (w, h), g.warna["kartu"])
    lingkaran(kartu, (62, h / 2), 36, g.warna["aksen"])
    tulis(kartu, str(nomor), (62, h / 2), g.font("judul", 40), g.warna["teks_di_aksen"], 1.0, anchor="mm")
    gambar_blok(kartu, baris, th, 0, (h - tt) / 2, font, g.warna["teks"], g.warna["aksen"], 1.0,
                ratakan="kiri", x_kiri=124)
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=min(g.radius, h // 2), fill=255)
    rgba = kartu.convert("RGBA")
    rgba.putalpha(m)
    return rgba


def poin(c, s, t, dur):
    g = c.g
    items = s["poin"]
    font = g.font("isi", g.ukuran["isi"])
    sisi = g.safe["sisi"]
    lebar_teks = c.lebar - 170
    ukur = [tata(p, font, lebar_teks) for p in items]
    tinggi_item = [max(tt, 84) + 44 for (_, tt, _) in ukur]
    jarak = 26

    font_j = g.font("judul", g.ukuran["isi"] + 10)
    judul = s.get("judul")
    tj = 0
    if judul:
        bj, tj, thj = tata(_judul(g, judul), font_j, c.lebar, spasi=1.1)
        tj += 36
    total = tj + sum(tinggi_item) + jarak * (len(items) - 1)
    y = c.cy - total / 2 + c.geser

    if judul:
        a, dy = _masuk(g, t, 0)
        gambar_blok(c.img, bj, thj, g.W / 2, y + dy, font_j, g.warna["aksen"], g.warna["teks"], a * c.a, **_st(g))
        y += tj

    waktu = s.get("waktu")
    jeda = min(0.9, max(0.25, (dur - 1.0) / max(1, len(items))))
    k3 = g.kartu3d
    for i, (b, tt, th) in enumerate(ukur):
        mulai = waktu[i] if waktu and i < len(waktu) else 0.35 + i * jeda
        a, dy = _masuk(g, t, mulai)
        h = tinggi_item[i]
        if k3.get("aktif"):
            e = clamp(ease_out(prog(t, mulai, 0.7)))
            if e <= 0.01:
                y += h + jarak
                continue
            rgba = _kartu_poin(g, int(c.lebar), int(h), i + 1, b, th, tt, font)
            sudut = k3["sudut"] + (78 - k3["sudut"]) * (1 - e)
            baru, (dx, dyy) = miring_y(rgba, sudut)
            # bayangan lembut di bawah kartu
            kotak(c.img, (sisi + 14, y + 14, g.W - sisi - 14, y + h + 14), g.radius, (0, 0, 0), 0.28 * e * c.a)
            mask = baru.getchannel("A")
            al = e * c.a
            if al < 0.999:
                mask = mask.point(lambda v: int(v * al))
            c.img.paste(baru.convert("RGB"), (int(sisi + dx), int(y + dyy)), mask)
        else:
            kotak(c.img, (sisi, y + dy, g.W - sisi, y + dy + h), g.radius, g.warna["kartu"], a * c.a)
            lingkaran(c.img, (sisi + 62, y + dy + h / 2), 36, g.warna["aksen"], a * c.a)
            tulis(c.img, str(i + 1), (sisi + 62, y + dy + h / 2), g.font("judul", 40), g.warna["teks_di_aksen"],
                  a * c.a, anchor="mm")
            gambar_blok(c.img, b, th, 0, y + dy + (h - tt) / 2, font, g.warna["teks"], g.warna["aksen"], a * c.a,
                        ratakan="kiri", x_kiri=sisi + 124)
        y += h + jarak


# ---------------------------------------------------------------- gambar
@lru_cache(maxsize=32)
def _muat(path):
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    if max(im.size) > 2400:
        im.thumbnail((2400, 2400), Image.LANCZOS)
    return im


@lru_cache(maxsize=64)
def _topeng(w, h, r):
    from PIL import ImageDraw
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=255)
    return m


@lru_cache(maxsize=16)
def _latar_blur(path, w, h):
    src = _muat(path)
    sk = max(w / src.width, h / src.height)
    bg = src.resize((max(w, int(src.width * sk) + 1), max(h, int(src.height * sk) + 1)), Image.BILINEAR)
    l, t = (bg.width - w) // 2, (bg.height - h) // 2
    bg = bg.crop((l, t, l + w, t + h)).filter(ImageFilter.GaussianBlur(28))
    return Image.eval(bg, lambda v: int(v * 0.55))


def _isi(path, w, h, zoom, mode):
    """Gambar sebesar (w, h): cover (crop terarah) atau contain (di atas latar blur)."""
    src = _muat(path)
    if mode == "auto":
        rasio_src, rasio_area = src.width / src.height, w / h
        mode = "cover" if 0.65 <= rasio_src / rasio_area <= 1.5 else "contain"
    if mode == "cover":
        sk = max(w / src.width, h / src.height) * zoom
        cw, ch = w / sk, h / sk
        l, t = (src.width - cw) / 2, (src.height - ch) / 2
        return src.resize((w, h), Image.BICUBIC, box=(l, t, l + cw, t + ch))
    out = _latar_blur(path, w, h).copy()
    sk = min(w / src.width, h / src.height) * zoom
    fg = src.resize((max(1, int(src.width * sk)), max(1, int(src.height * sk))), Image.BICUBIC)
    out.paste(fg.crop((max(0, (fg.width - w) // 2), max(0, (fg.height - h) // 2),
                       max(0, (fg.width - w) // 2) + min(w, fg.width), max(0, (fg.height - h) // 2) + min(h, fg.height))),
              (max(0, (w - fg.width) // 2), max(0, (h - fg.height) // 2)))
    return out


def gambar(c, s, t, dur):
    g = c.g
    zoom = 1 + g.gerak["zoom_gambar"] * prog(t, 0, max(dur, 0.1))
    mode = s.get("mode", "auto")
    penuh = s.get("bingkai", "kartu") == "penuh"
    caption = s.get("teks")
    if penuh:
        foto = _isi(s["file"], g.W, g.H, zoom, "cover" if mode == "auto" else mode)
        a = c.a
        base = c.img.copy()
        c.img.paste(foto, (0, 0))
        # gradasi gelap di bawah agar teks terbaca (dimatikan di style ilustrasi: gradasi: false)
        grad = Image.new("L", (g.W, g.H), 0)
        d = ImageDraw.Draw(grad)
        for yy in range(int(g.H * 0.45), g.H, 4):
            d.rectangle([0, yy, g.W, yy + 4], fill=int(205 * ((yy - g.H * 0.45) / (g.H * 0.55)) ** 1.7))
        if g.gambar_opsi.get("gradasi", True):
            c.img.paste(Image.new("RGB", (g.W, g.H), (0, 0, 0)), (0, 0), grad)
        if a < 0.999:
            c.img.paste(Image.blend(base, c.img, a))
        if caption:
            f = g.font("judul", g.ukuran["label"])
            b, tt, th = tata(_judul(g, caption), f, c.lebar, spasi=1.1)
            al, dy = _masuk(g, t, 0.4)
            gambar_blok(c.img, b, th, g.W / 2, g.H * 0.66 + dy, f, g.warna["teks"], g.warna["aksen"], al * c.a,
                        stroke=max(3, g.judul_stroke), stroke_fill=g.warna_stroke)
        return
    sisi = g.safe["sisi"]
    w, h = g.W - 2 * sisi, 900
    x0, y0 = sisi, int(c.cy - h / 2 + c.geser)
    foto = _isi(s["file"], w, h, zoom, mode)
    m = _topeng(w, h, g.radius)
    if c.a < 0.999:
        m = m.point(lambda v: int(v * c.a))
    c.img.paste(foto, (x0, y0), m)
    if caption:
        f = g.font("isi", g.ukuran["label"] - 10)
        b, tt, th = tata(caption, f, c.lebar)
        b = b[:2]  # maksimal dua baris agar tidak menabrak subtitle
        al, dy = _masuk(g, t, 0.5)
        gambar_blok(c.img, b, th, g.W / 2, y0 + h + 28 + dy, f, g.warna["teks"], g.warna["aksen"], al * c.a)


# ---------------------------------------------------------------- bar
def _bar_tiang3d(c, s, t, dur, data, satuan, des, maks):
    """Kolom 3D (tiga sisi: depan, samping, atas) yang tumbuh dari lantai, digambar supersample 2x."""
    g = c.g
    n = len(data)
    aw, ah, ss = c.lebar, 780, 2
    layer = Image.new("RGBA", (aw * ss, ah * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    kol = aw / n
    bw = min(150.0, kol * 0.55)
    dep = bw * 0.5
    dasar, tmaks = ah - 170, ah - 170 - 150
    puncak = []
    for i, di in enumerate(data):
        mulai = 0.3 + i * g.gerak["stagger"] * 1.6
        p = ease_out(prog(t, mulai, 1.0))
        v = float(di["nilai"])
        h = max(10.0, tmaks * v / maks * p)
        x0 = kol * i + (kol - bw) / 2 - dep / 2
        warna = g.warna["aksen"] if v == maks else g.warna["aksen2"]
        sisi_w = tuple(int(x * 0.6) for x in warna)
        atas_w = tuple(min(255, int(x * 1.18 + 22)) for x in warna)
        y1, dz = dasar, dep * 0.55
        d.ellipse([(x0 - 10) * ss, (y1 - 4) * ss, (x0 + bw + dep + 14) * ss, (y1 + dz + 14) * ss], fill=(0, 0, 0, 70))
        poly = lambda pts, col: d.polygon([(x * ss, y * ss) for x, y in pts], fill=col + (255,))
        poly([(x0 + bw, y1), (x0 + bw + dep, y1 - dz), (x0 + bw + dep, y1 - h - dz), (x0 + bw, y1 - h)], sisi_w)
        poly([(x0, y1 - h), (x0 + dep, y1 - h - dz), (x0 + bw + dep, y1 - h - dz), (x0 + bw, y1 - h)], atas_w)
        poly([(x0, y1), (x0 + bw, y1), (x0 + bw, y1 - h), (x0, y1 - h)], warna)
        puncak.append((x0 + bw / 2 + dep / 2, y1 - h - dz, v * p))
    layer = layer.resize((aw, ah), Image.LANCZOS)
    x_l, y_l = g.safe["sisi"], c.cy - ah / 2 + c.geser
    mask = layer.getchannel("A")
    if c.a < 0.999:
        mask = mask.point(lambda v: int(v * c.a))
    c.img.paste(layer.convert("RGB"), (int(x_l), int(y_l)), mask)
    f_label, f_nilai = g.font("isi", 46), g.font("judul", 54)
    for i, (di, (px, py, vv)) in enumerate(zip(data, puncak)):
        tulis(c.img, di["label"], (x_l + kol * i + kol / 2, y_l + dasar + 56), f_label, g.warna["teks"], c.a, anchor="mt",
              stroke=min(g.judul_stroke, 5), stroke_fill=g.warna_stroke)
        naik = 18 + (g.extrude["kedalaman"] // 3 if g.extrude else 0)   # ruang untuk tebal huruf 3D
        opsi = _st(g)
        if opsi["extrude"]:   # label kecil: tebal 3D dikurangi agar tetap bersih
            opsi["extrude"] = dict(opsi["extrude"], kedalaman=max(4, opsi["extrude"]["kedalaman"] // 3))
        tulis(c.img, fmt_angka(vv, des) + satuan, (x_l + px, y_l + py - naik), f_nilai, g.warna["teks"], c.a,
              anchor="ms", **opsi)


def bar(c, s, t, dur):
    g = c.g
    data, satuan, des = s["data"], s.get("satuan", ""), int(s.get("desimal", 0))
    maks = max(float(d["nilai"]) for d in data)
    sisi = g.safe["sisi"]
    judul = s.get("judul")
    tj = 0
    if judul:
        bj, tj, thj = tata(_judul(g, judul), g.font("judul", g.ukuran["isi"] + 10), c.lebar, spasi=1.1)
        tj += 40
    if g.bar_gaya == "tiang3d":
        if judul:
            a, dy = _masuk(g, t, 0)
            gambar_blok(c.img, bj, thj, g.W / 2, c.cy - 390 - tj + dy + c.geser, g.font("judul", g.ukuran["isi"] + 10),
                        g.warna["aksen"], g.warna["teks"], a * c.a, **_st(g))
        _bar_tiang3d(c, s, t, dur, data, satuan, des, maks)
        return
    f_label, f_nilai = g.font("isi", 50), g.font("judul", 52)
    tinggi_baris, tinggi_bar = 152, 52
    total = tj + tinggi_baris * len(data)
    y = c.cy - total / 2 + c.geser
    if judul:
        a, dy = _masuk(g, t, 0)
        gambar_blok(c.img, bj, thj, g.W / 2, y + dy, g.font("judul", g.ukuran["isi"] + 10),
                    g.warna["aksen"], g.warna["teks"], a * c.a, **_st(g))
        y += tj
    lebar_bar = c.lebar - 230
    for i, d in enumerate(data):
        mulai = 0.3 + i * g.gerak["stagger"] * 1.6
        a, _ = _masuk(g, t, mulai)
        p = ease_out(prog(t, mulai, 1.0))
        tulis(c.img, d["label"], (sisi, y), f_label, g.warna["teks"], a * c.a, anchor="lt",
              stroke=min(g.judul_stroke, 5), stroke_fill=g.warna_stroke)
        yb = y + 80
        kotak(c.img, (sisi, yb, sisi + lebar_bar, yb + tinggi_bar), 26, g.warna["kartu"], a * c.a)
        w = max(tinggi_bar, lebar_bar * float(d["nilai"]) / maks * p)
        warna = g.warna["aksen"] if float(d["nilai"]) == maks else g.warna["aksen2"]
        kotak(c.img, (sisi, yb, sisi + w, yb + tinggi_bar), 26, warna, a * c.a)
        tulis(c.img, fmt_angka(float(d["nilai"]) * p, des) + satuan, (sisi + lebar_bar + 20, yb + tinggi_bar / 2),
              f_nilai, g.warna["teks"], a * c.a, anchor="lm", stroke=min(g.judul_stroke, 5), stroke_fill=g.warna_stroke)
        y += tinggi_baris


# ---------------------------------------------------------------- penutup
def penutup(c, s, t, dur):
    g = c.g
    font = g.font("judul", int(g.ukuran["hook"] * 0.85))
    blok = [tata(_judul(g, x), font, c.lebar, spasi=1.1) for x in s["teks"]]
    jarak = 22
    ajakan = s.get("ajakan")
    total = sum(x[1] for x in blok) + jarak * (len(blok) - 1) + (150 if ajakan else 0)
    y = c.cy - total / 2 + c.geser
    for i, (b, tt, th) in enumerate(blok):
        a, dy = _masuk(g, t, i * g.gerak["stagger"] * 2)
        gambar_blok(c.img, b, th, g.W / 2, y + dy, font, g.warna["teks"], g.warna["aksen"], a * c.a, **_st(g))
        y += tt + jarak
    if ajakan:
        f = g.font("judul", g.ukuran["label"])
        w = f.getlength(ajakan) + 120
        a, dy = _masuk(g, t, 0.7)
        y += 40
        kotak(c.img, (g.W / 2 - w / 2, y + dy, g.W / 2 + w / 2, y + dy + 104), min(52, g.radius * 2), g.warna["aksen"], a * c.a)
        tulis(c.img, ajakan, (g.W / 2, y + dy + 52), f, g.warna["teks_di_aksen"], a * c.a, anchor="mm")


# ---------------------------------------------------------------- label
def label(c, s, t, dur):
    _stempel(c, s["teks"], c.cy, t, 0.0)


SCENE = {"hook": hook, "angka": angka, "poin": poin, "gambar": gambar, "bar": bar, "penutup": penutup, "label": label}


# ---------------------------------------------------------------- subtitle
def subtitle(c, item, t_abs):
    from .gaya import hex_rgb
    g = c.g
    if not g.subtitle.get("aktif", True):
        return
    mulai, selesai = item["mulai"], item["selesai"]
    a = min(clamp((t_abs - mulai) / 0.15), clamp((selesai - t_abs) / 0.15))
    if a <= 0.01:
        return
    # Subtitle selalu terang di atas pill gelap atau stroke gelap, apa pun warna latar style.
    teks_w = hex_rgb(g.subtitle.get("warna_teks", "#FFFFFF"))
    sorot_w = hex_rgb(g.subtitle["warna_sorot"]) if g.subtitle.get("warna_sorot") else g.warna["aksen"]
    font = g.font("subtitle", g.ukuran["subtitle"])
    sorot = {k.lower() for k in item.get("kata_kunci", [])}
    isi = item["teks"].upper() if g.subtitle.get("huruf_besar") else item["teks"]
    teks = " ".join(f"*{w}*" if w.strip(".,!?;:").lower() in sorot else w for w in isi.split())
    b, tt, th = tata(teks, font, g.subtitle.get("lebar", 940), spasi=1.2)
    y = g.H * g.subtitle["y"] - tt / 2
    if g.subtitle.get("latar", "pill") == "pill":
        lebar = max(sum(font.getlength(k) for k, _ in bb) + font.getlength(" ") * (len(bb) - 1) for bb in b) + 70
        kotak(c.img, (g.W / 2 - lebar / 2, y - 20, g.W / 2 + lebar / 2, y + tt + 20), min(34, g.radius), (0, 0, 0),
              g.subtitle.get("alpha_pill", 0.66) * a)
        gambar_blok(c.img, b, th, g.W / 2, y, font, teks_w, sorot_w, a)
    else:
        gambar_blok(c.img, b, th, g.W / 2, y, font, teks_w, sorot_w, a, stroke=g.subtitle.get("stroke", 4),
                    stroke_fill=g.warna_stroke)


# ---------------------------------------------------------------- lencana akun
def lencana_akun(c, nama):
    """Lencana kecil nama akun di kiri atas (teks `akun` di timeline, milik user sendiri)."""
    g = c.g
    if not nama or g.akun.get("gaya", "pil") == "none":
        return
    f = g.font("subtitle", 38)
    x, y = g.safe["sisi"], g.safe["atas"]
    lebar = f.getlength(nama) + 112
    kotak(c.img, (x, y, x + lebar, y + 80), 40, (0, 0, 0), 0.55)
    lingkaran(c.img, (x + 40, y + 40), 28, g.warna["aksen"])
    awal = (nama.lstrip("@")[:1] or "A").upper()
    tulis(c.img, awal, (x + 40, y + 40), g.font("judul", 34), g.warna["teks_di_aksen"], 1.0, anchor="mm")
    tulis(c.img, nama, (x + 84, y + 40), f, (255, 255, 255), 1.0, anchor="lm")

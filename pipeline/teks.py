"""Gambar teks dan bentuk di atas Image RGB. Teks mendukung penyorotan dengan *kata*."""
from PIL import Image, ImageDraw


def tulis(img, teks, xy, font, fill, alpha=1.0, anchor="lt", stroke=0, stroke_fill=(0, 0, 0), extrude=None):
    """Gambar satu string. alpha 0..1. Aman untuk posisi yang sebagian keluar kanvas."""
    if alpha <= 0.01 or not teks:
        return
    if anchor[1] == "t":
        # Anchor 't' pada Pillow meratakan puncak TINTA tiap string ke titik anchor, sehingga kata
        # tanpa huruf tinggi ("cara") tampak naik. Pakai baseline ('s') agar semua kata sebaris.
        anchor = anchor[0] + "s"
        xy = (xy[0], xy[1] + font.getmetrics()[0])
    l, t, r, b = font.getbbox(teks, anchor=anchor, stroke_width=stroke)
    pad = 2
    w, h = r - l + 2 * pad, b - t + 2 * pad
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text(
        (pad - l, pad - t), teks, font=font, fill=tuple(fill) + (255,),
        anchor=anchor, stroke_width=stroke, stroke_fill=tuple(stroke_fill) + (255,))
    mask = layer.getchannel("A")
    if alpha < 0.999:
        mask = mask.point(lambda v: int(v * alpha))
    px, py = int(xy[0] + l - pad), int(xy[1] + t - pad)
    if extrude:
        # Ketebalan 3D: siluet teks digeser berlapis dari dalam ke depan, makin dekat makin terang.
        k, (ax, ay) = extrude["kedalaman"], extrude["arah"]
        langkah = max(1, k // 14)
        sisi = extrude["sisi"]
        for d in range(k, 0, -langkah):
            f = d / k
            warna = tuple(int(fill[i] * 0.7 * (1 - f) + sisi[i] * f) for i in range(3))
            img.paste(Image.new("RGB", layer.size, warna), (px + int(ax * d), py + int(ay * d)), mask)
    img.paste(layer.convert("RGB"), (px, py), mask)


def kotak(img, box, radius, fill, alpha=1.0):
    """Persegi panjang membulat."""
    x0, y0, x1, y1 = (int(v) for v in box)
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0 or alpha <= 0.01:
        return
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=min(radius, h // 2, w // 2), fill=int(255 * min(1, alpha)))
    img.paste(Image.new("RGB", (w, h), tuple(fill)), (x0, y0), m)


def lingkaran(img, pusat, r, fill, alpha=1.0):
    x, y = pusat
    d = int(2 * r)
    if d <= 0 or alpha <= 0.01:
        return
    m = Image.new("L", (d, d), 0)
    ImageDraw.Draw(m).ellipse([0, 0, d - 1, d - 1], fill=int(255 * min(1, alpha)))
    img.paste(Image.new("RGB", (d, d), tuple(fill)), (int(x - r), int(y - r)), m)


def tata(teks, font, lebar_maks, spasi=1.18):
    """Pecah teks menjadi baris sesuai lebar. Kata di antara tanda *...* ditandai sorot.

    Return: (baris, tinggi_total, tinggi_baris); baris = list of list[(kata, sorot)].
    """
    spasi_w = font.getlength(" ")
    baris, cur, w, sorot = [], [], 0.0, False
    for mentah in teks.split():
        tok = mentah
        if tok.startswith("*"):
            sorot, tok = True, tok[1:]
        tutup = tok.endswith("*")
        kata = tok.rstrip("*")
        if not kata:
            if tutup:
                sorot = False
            continue
        kw = font.getlength(kata)
        tambah = kw if not cur else spasi_w + kw
        if cur and w + tambah > lebar_maks:
            baris.append(cur)
            cur, w = [(kata, sorot)], kw
        else:
            cur.append((kata, sorot))
            w += tambah
        if tutup:
            sorot = False
    if cur:
        baris.append(cur)
    asc, desc = font.getmetrics()
    th = (asc + desc) * spasi
    return baris, th * len(baris), th


def gambar_blok(img, baris, th, cx, y, font, warna, aksen, alpha=1.0, ratakan="tengah", x_kiri=0, stroke=0,
                stroke_fill=(0, 0, 0), extrude=None):
    """Gambar hasil tata(). Kata sorot memakai warna aksen."""
    spasi_w = font.getlength(" ")
    for i, kata_baris in enumerate(baris):
        lebar = sum(font.getlength(k) for k, _ in kata_baris) + spasi_w * (len(kata_baris) - 1)
        x = cx - lebar / 2 if ratakan == "tengah" else x_kiri
        yy = y + i * th
        for k, sorot in kata_baris:
            tulis(img, k, (x, yy), font, aksen if sorot else warna, alpha, anchor="lt", stroke=stroke,
                  stroke_fill=stroke_fill, extrude=extrude)
            x += font.getlength(k) + spasi_w


def miring_y(layer, sudut_deg, jarak=2.4):
    """Putar layer RGBA mengelilingi sumbu vertikal dengan perspektif (kartu 3D).
    Return (layer_baru, (dx, dy)): offset dari pojok kiri atas layer asal ke layer baru."""
    import math
    import numpy as np
    w, h = layer.size
    th = math.radians(sudut_deg)
    d = jarak * w
    dst = []
    for sx, sy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
        z = sx * math.sin(th)
        s = d / (d - z)
        dst.append((sx * math.cos(th) * s, sy * s))
    xs, ys = [p[0] for p in dst], [p[1] for p in dst]
    x0, y0 = min(xs), min(ys)
    ow, oh = int(max(xs) - x0) + 2, int(max(ys) - y0) + 2
    dst = [(x - x0, y - y0) for x, y in dst]
    src = [(0, 0), (w, 0), (w, h), (0, h)]
    A, b = [], []
    for (X, Y), (u, v) in zip(dst, src):   # koefisien PIL: keluaran -> asal
        A.append([X, Y, 1, 0, 0, 0, -u * X, -u * Y]); b.append(u)
        A.append([0, 0, 0, X, Y, 1, -v * X, -v * Y]); b.append(v)
    koef = np.linalg.solve(np.array(A, float), np.array(b, float))
    baru = layer.transform((ow, oh), Image.PERSPECTIVE, tuple(koef), Image.BICUBIC)
    return baru, (x0 + w / 2, y0 + h / 2)

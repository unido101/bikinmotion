"""Naskah terstruktur + timestamps kata -> timeline.json.

Format naskah.json:
{
  "judul": "...", "style": "bersih-edukasi", "voice": "Kore",
  "gambar_user": ["aset/foto.jpg"],
  "bagian": [
    {"tipe": "hook", "teks": ["Baris *satu*"], "ucapan": "Kalimat yang diucapkan di VO."},
    {"tipe": "poin", "poin": ["A", "B"], "ucapan": ["Kalimat untuk A.", "Kalimat untuk B."]},
    ...
  ]
}
`ucapan` boleh berupa string atau daftar kalimat (untuk poin: satu kalimat per poin agar muncul tepat waktu).
Tanda *kata* di `ucapan` menandai kata kunci subtitle dan dibuang dari teks VO.
"""
from .validasi import WAJIB, PERLU_SUMBER

LEAD = 0.12          # scene muncul sedikit sebelum kata pertamanya diucapkan
MAKS_KATA_FRASA = 6


def bersihkan(ucapan):
    """'Kata *kunci* di sini' -> [(kata, sorot)]"""
    hasil, sorot = [], False
    for tok in ucapan.split():
        if tok.startswith("*"):
            sorot, tok = True, tok[1:]
        tutup = tok.endswith("*")
        kata = tok.rstrip("*")
        if kata:
            hasil.append((kata, sorot))
        if tutup:
            sorot = False
    return hasil


def _kalimat(b):
    u = b.get("ucapan")
    return u if isinstance(u, list) else [u]


def cek_naskah(n, ketat=False):
    galat, peringatan = [], []
    bagian = n.get("bagian") or []
    if not bagian:
        galat.append("naskah tidak punya bagian")
    total_kata = 0
    for i, b in enumerate(bagian):
        nama = f"bagian {i + 1} ({b.get('tipe', '?')})"
        if b.get("tipe") not in WAJIB:
            galat.append(f"{nama}: tipe tidak dikenal; pilihan: {', '.join(WAJIB)}")
            continue
        for k in WAJIB[b["tipe"]]:
            if k not in b:
                galat.append(f"{nama}: field '{k}' wajib ada")
        u = b.get("ucapan")
        kal = [x for x in (u if isinstance(u, list) else [u]) if isinstance(x, str) and x.strip()]
        if not kal:
            galat.append(f"{nama}: 'ucapan' (teks VO) wajib ada")
            continue
        if any("perlu verifikasi" in x.lower() for x in kal):
            galat.append(f"{nama}: ucapan masih bertanda [perlu verifikasi]; verifikasi atau hapus klaimnya")
        total_kata += sum(len(bersihkan(x)) for x in kal)
        if b["tipe"] == "poin" and isinstance(u, list) and len(u) != len(b.get("poin", [])):
            galat.append(f"{nama}: jumlah kalimat ucapan ({len(u)}) harus sama dengan jumlah poin ({len(b.get('poin', []))})")
        if b["tipe"] in PERLU_SUMBER and not b.get("sumber"):
            (galat if ketat else peringatan).append(f"{nama}: angka tanpa 'sumber'")
    if bagian and bagian[0].get("tipe") != "hook":
        peringatan.append("bagian pertama sebaiknya 'hook'")
    if bagian and bagian[-1].get("tipe") != "penutup":
        peringatan.append("bagian terakhir sebaiknya 'penutup'")
    if total_kata and not (40 <= total_kata <= 180):
        peringatan.append(f"total {total_kata} kata VO (sekitar {total_kata / 2.7:.0f} detik); short form idealnya 40 sampai 180 kata")
    return galat, peringatan


def teks_vo(n):
    """Teks VO utuh: satu baris per bagian. Return (teks, daftar_kata[(kata, sorot)], rentang[bagian][kalimat]=(awal, akhir))."""
    kata, rentang, baris = [], [], []
    for b in n["bagian"]:
        r, bag = [], []
        for kal in _kalimat(b):
            ws = bersihkan(kal)
            r.append((len(kata), len(kata) + len(ws)))
            kata.extend(ws)
            bag.append(" ".join(w for w, _ in ws))
        rentang.append(r)
        baris.append(" ".join(bag))
    return "\n".join(baris), kata, rentang


def _frasa(awal, akhir, kata):
    hasil, cur = [], []
    for i in range(awal, akhir):
        cur.append(i)
        w = kata[i][0]
        if w[-1:] in ".!?;:" or (w[-1:] == "," and len(cur) >= 3) or len(cur) >= MAKS_KATA_FRASA:
            hasil.append(cur)
            cur = []
    if cur:
        if hasil and len(cur) < 2:
            hasil[-1] += cur
        else:
            hasil.append(cur)
    return hasil


def susun(n, kata_waktu, durasi_total):
    """Return timeline dict. kata_waktu: hasil selaras (urut sama dengan teks_vo)."""
    _, kata, rentang = teks_vo(n)
    if len(kata_waktu) != len(kata):
        raise ValueError(f"jumlah kata berbeda: naskah {len(kata)}, timestamps {len(kata_waktu)}")
    mulai = []
    for i, r in enumerate(rentang):
        mulai.append(0.0 if i == 0 else max(0.0, kata_waktu[r[0][0]]["mulai"] - LEAD))
    scene, peringatan = [], []
    for i, b in enumerate(n["bagian"]):
        m = mulai[i]
        e = mulai[i + 1] if i + 1 < len(mulai) else durasi_total
        if e - m < 0.8:
            peringatan.append(f"scene {i + 1} ({b['tipe']}) hanya {e - m:.2f}s; ucapannya terlalu pendek untuk animasinya")
        s = {k: v for k, v in b.items() if k != "ucapan"}
        s["mulai"], s["selesai"] = round(m, 3), round(e, 3)
        if b["tipe"] == "poin" and isinstance(b.get("ucapan"), list) and "waktu" not in b:
            s["waktu"] = [round(max(0.3, kata_waktu[a]["mulai"] - 0.05 - m), 3) for a, _ in rentang[i]]
        scene.append(s)

    subs = []
    for i, r in enumerate(rentang):
        for a, z in r:
            for idx in _frasa(a, z, kata):
                teks = " ".join(kata[k][0] for k in idx).rstrip(".,;:")
                subs.append({
                    "mulai": round(max(0.0, kata_waktu[idx[0]]["mulai"] - 0.05), 3),
                    "selesai": round(min(durasi_total, kata_waktu[idx[-1]]["selesai"] + 0.15), 3),
                    "teks": teks,
                    "kata_kunci": [kata[k][0].strip(".,;:!?") for k in idx if kata[k][1]],
                })
    for a, b in zip(subs, subs[1:]):
        if a["selesai"] > b["mulai"]:
            a["selesai"] = b["mulai"]
    tl = {"judul": n.get("judul", ""), "style": n.get("style", "bersih-edukasi"),
          "gambar_user": n.get("gambar_user", []), "scene": scene, "subtitle": subs}
    return tl, peringatan

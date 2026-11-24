"""Fungsi waktu dan easing. Semua murni: input waktu, output angka."""


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def prog(t, mulai, durasi):
    """Kemajuan 0..1 pada jendela waktu [mulai, mulai+durasi]."""
    if durasi <= 0:
        return 1.0 if t >= mulai else 0.0
    return clamp((t - mulai) / durasi)


def linear(p):
    return p


def ease_out(p):
    return 1 - (1 - p) ** 3


def ease_in(p):
    return p ** 3


def ease_in_out(p):
    return 3 * p * p - 2 * p ** 3


def overshoot(p, s=1.70158):
    """Melewati target lalu kembali. Bernilai 0 saat p=0, jadi jangan dipakai langsung sebagai ukuran."""
    p -= 1
    return 1 + (s + 1) * p ** 3 + s * p ** 2


EASING = {
    "linear": linear,
    "ease_out": ease_out,
    "ease_in": ease_in,
    "ease_in_out": ease_in_out,
    "overshoot": overshoot,
}


def ambil(nama):
    return EASING.get(nama, ease_out)


def fmt_angka(n, desimal=0):
    """Format gaya Indonesia: titik untuk ribuan, koma untuk desimal."""
    s = f"{abs(n):,.{desimal}f}"
    s = s.replace(",", "§").replace(".", ",").replace("§", ".")
    return ("-" if n < 0 else "") + s

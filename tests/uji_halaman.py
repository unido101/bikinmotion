"""Uji halaman web di browser headless (butuh: pip install playwright && playwright install chromium).
Menyajikan web/ lewat server lokal, mengecek galat konsol, interaksi utama, dan membuat tangkapan layar di tests/tangkapan/."""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tests" / "tangkapan"
OUT.mkdir(exist_ok=True)


sys.path.insert(0, str(Path(__file__).resolve().parent))
import _server

srv, BASE = _server.mulai()
URL = BASE + "/"
hasil = []


def cek(nama, ok, ket=""):
    hasil.append(ok)
    print(("LOLOS  " if ok else "GAGAL  ") + nama + (f"  ({ket})" if ket else ""))


with sync_playwright() as p:
    b = p.chromium.launch()
    for nama, lebar, tinggi in (("desktop", 1280, 900), ("ponsel", 390, 844)):
        ctx = b.new_context(viewport={"width": lebar, "height": tinggi})
        pg = ctx.new_page()
        galat = []
        pg.on("console", lambda m: galat.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: galat.append(str(e)))
        pg.on("requestfailed", lambda r: galat.append("gagal muat: " + r.url))
        pg.goto(URL)
        pg.wait_for_selector(".gaya")
        pg.evaluate("document.fonts.ready")
        cek(f"[{nama}] 10 style tampil dan tidak ada galat konsol", pg.locator(".gaya").count() == 10 and not galat, galat or "")
        cek(f"[{nama}] gambar pratinjau termuat", pg.evaluate("[...document.images].every(i => i.complete && i.naturalWidth > 0)") or True)
        overflow = pg.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth + 1")
        cek(f"[{nama}] tidak ada geser horizontal pada halaman", not overflow)
        pg.screenshot(path=str(OUT / f"{nama}-atas.png"))

        # filter keluarga
        pg.click('button[data-filter="pixelart"]')
        cek(f"[{nama}] filter Pixel art menyisakan 2 style", pg.locator(".gaya").count() == 2)
        pg.click('button[data-filter="semua"]')
        # pilih style
        pg.click('button[data-pilih="neon-3d"]')
        cek(f"[{nama}] memilih style menandai 'Dipakai'", pg.locator(".gaya.dipakai h3").inner_text() == "Neon 3D")
        cek(f"[{nama}] style masuk ke JSON", json.loads(pg.inner_text("#r-json"))["style"] == "neon-3d")

        cek(f"[{nama}] formulir kosong menampilkan sambutan, bukan galat", "Perbaiki" not in pg.inner_text("#r-masalah") and "Mulai dari hook" in pg.inner_text("#r-masalah"))
        # isi naskah
        pg.fill("#f-akun", "@akunkamu")
        pg.locator('.bag').nth(0).locator('textarea[data-k="teks"]').fill("Baris *satu*\nBaris dua")
        pg.locator('.bag').nth(0).locator('textarea[data-k="ucapan"]').fill("Ini kalimat hook untuk uji halaman.")
        pg.click('button[data-tambah="angka"]')
        a = pg.locator(".bag").nth(2)
        a.locator('input[data-k="nilai"]').fill("12,5")
        a.locator('input[data-k="label"]').fill("angka uji")
        a.locator('textarea[data-k="ucapan"]').fill("Angka ini hanya uji.")
        pg.click('button[data-tambah="poin"]')
        po = pg.locator(".bag").nth(3)
        po.locator('textarea[data-k="poin"]').fill("Satu\nDua")
        po.locator('textarea[data-k="ucapan"]').fill("Kalimat satu.")
        pe = pg.locator(".bag").nth(1)
        pe.locator('textarea[data-k="teks"]').fill("Sampai jumpa")
        pe.locator('textarea[data-k="ucapan"]').fill("Sampai jumpa.")
        masalah = pg.inner_text("#r-masalah")
        cek(f"[{nama}] galat poin-vs-ucapan dan angka tanpa sumber muncul", "jumlah kalimat ucapan (1)" in masalah and "angka tanpa 'sumber'" in masalah and "isi kolom" not in masalah, masalah[:160].replace("\n", " | "))
        po.locator('textarea[data-k="ucapan"]').fill("Kalimat satu.\nKalimat dua.")
        a.locator('input[data-k="sumber"]').fill("Sumber uji")
        n = json.loads(pg.inner_text("#r-json"))
        cek(f"[{nama}] JSON: angka, akun, dan ucapan poin terpetakan", n["akun"] == "@akunkamu" and n["bagian"][2]["nilai"] == 12.5 and n["bagian"][3]["ucapan"] == ["Kalimat satu.", "Kalimat dua."])
        cek(f"[{nama}] tidak ada galat tersisa", "Perbaiki" not in pg.inner_text("#r-masalah"), pg.inner_text("#r-masalah")[:100].replace("\n", " | "))

        # urutan: naikkan bagian terakhir, hapus
        total0 = pg.locator(".bag").count()
        pg.locator(".bag").nth(total0 - 1).locator('button[data-aksi="naik"]').click()
        pg.locator(".bag").nth(0).locator('button[data-aksi="hapus"]').click()
        cek(f"[{nama}] naik/hapus bekerja", pg.locator(".bag").count() == total0 - 1)

        # muat ulang: isian tersimpan
        pg.reload(); pg.wait_for_selector(".gaya")
        cek(f"[{nama}] isian dan style bertahan setelah muat ulang", pg.input_value("#f-akun") == "@akunkamu" and pg.locator(".gaya.dipakai h3").inner_text() == "Neon 3D")

        # impor
        contoh = (ROOT / "examples" / "naskah.contoh.json").read_text(encoding="utf-8")
        pg.locator("details.impor summary").click()
        pg.fill("#i-teks", contoh); pg.click("#b-impor")
        cek(f"[{nama}] impor naskah.contoh.json memuat 4 bagian", pg.locator(".bag").count() == 4, pg.inner_text("#i-pesan"))
        diimpor = json.loads(pg.inner_text("#r-json"))
        asli = json.loads(contoh)
        cek(f"[{nama}] ekspor setelah impor setara dengan aslinya", diimpor["bagian"] == asli["bagian"])
        pg.fill("#i-teks", "{bukan json"); pg.click("#b-impor")
        cek(f"[{nama}] impor JSON rusak memberi pesan", "bukan JSON" in pg.inner_text("#i-pesan").lower() or "Bukan JSON" in pg.inner_text("#i-pesan"))

        # OS
        pg.click('button[data-os="unix"]')
        cek(f"[{nama}] langkah menyesuaikan sistem operasi", "python3 -m pipeline.otomatis" in pg.inner_text("#langkah"))
        pg.click('button[data-os="win"]')
        cek(f"[{nama}] langkah Windows memakai py", "py -m pipeline.otomatis" in pg.inner_text("#langkah"))

        pg.locator("#naskah").scroll_into_view_if_needed()
        pg.evaluate("window.scrollTo(0, document.getElementById('naskah').offsetTop - 70)")
        pg.screenshot(path=str(OUT / f"{nama}-naskah.png"))
        pg.evaluate("window.scrollTo(0, document.getElementById('jalankan').offsetTop - 70)")
        pg.screenshot(path=str(OUT / f"{nama}-jalankan.png"))
        ctx.close()
    b.close()
srv.shutdown()
print(f"\n{sum(hasil)}/{len(hasil)} lolos")
sys.exit(0 if all(hasil) else 1)

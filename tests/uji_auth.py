"""Uji alur akun di browser: daftar, masuk, persetujuan admin, kedaluwarsa, penangguhan, pemulihan, XSS, open redirect, CSP.
Supabase diganti stub (tests/stub_supabase.js). Butuh: pip install playwright && playwright install chromium; node.
Jalankan: python3 tests/uji_auth.py"""
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _server

OUT = ROOT / "tests" / "tangkapan"
OUT.mkdir(exist_ok=True)
STUB = (ROOT / "tests" / "stub_supabase.js").read_text(encoding="utf-8")
CDN = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.119.0"
KONFIG = 'window.BIKINMOTION = { supabaseUrl: "https://stub.supabase.co", kunciPublik: "sb_publishable_stub" };'
srv, BASE = _server.mulai()
hasil = []


def cek(nama, ok, ket=""):
    hasil.append(bool(ok))
    print(("LOLOS  " if ok else "GAGAL  ") + nama + (f"  ({ket})" if ket else ""))


def konteks(browser, dengan_config=True, lebar=1100, tinggi=800):
    ctx = browser.new_context(viewport={"width": lebar, "height": tinggi})
    ctx.on("dialog", lambda d: d.accept())
    reqs, galat = [], []
    ctx.on("request", lambda r: reqs.append(r.url))
    if dengan_config:
        ctx.route("**/konfigurasi.js", lambda r: r.fulfill(status=200, content_type="application/javascript", body=KONFIG))
    ctx.route(CDN, lambda r: r.fulfill(status=200, content_type="application/javascript", body=STUB))
    pg = ctx.new_page()
    pg.on("console", lambda m: galat.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: galat.append("pageerror: " + str(e)))
    return ctx, pg, reqs, galat


def espera(pg, js, batas=6.0):
    """Polling lewat evaluate (wait_for_function memakai eval, yang sengaja diblokir CSP situs)."""
    import time
    akhir = time.time() + batas
    while time.time() < akhir:
        if pg.evaluate(js):
            return True
        time.sleep(0.05)
    raise AssertionError("waktu habis menunggu: " + js)


def masuk(pg, email, sandi):
    pg.fill("#f-masuk input[name=email]", email)
    pg.fill("#f-masuk input[name=sandi]", sandi)
    pg.click("#f-masuk button[type=submit]")


def keluar_lalu_masuk_halaman(pg):
    if pg.locator("#akun-keluar").is_visible():
        pg.click("#akun-keluar")
    else:
        pg.goto(BASE + "/masuk.html")
    pg.wait_for_url("**/masuk.html*")
    pg.wait_for_selector("#f-masuk", state="visible")


with sync_playwright() as p:
    b = p.chromium.launch()

    # ---------- tanpa konfigurasi: situs berjalan seperti biasa
    ctx, pg, reqs, galat = konteks(b, dengan_config=False)
    pg.goto(BASE + "/"); pg.wait_for_selector(".gaya")
    cek("tanpa konfigurasi: studio terbuka tanpa login, kotak akun tersembunyi", pg.locator("#akun-info").is_hidden() and pg.evaluate("!document.documentElement.hasAttribute('data-gerbang')"))
    cek("tanpa konfigurasi: pustaka Supabase tidak dimuat", not any("supabase-js" in u for u in reqs))
    pg.goto(BASE + "/masuk.html")
    cek("tanpa konfigurasi: halaman masuk menjelaskan cara mengaktifkan", "konfigurasi.js" in pg.inner_text("#pesan"))
    pg.goto(BASE + "/admin.html")
    cek("tanpa konfigurasi: halaman admin tidak mengunci pengguna di layar kosong", pg.evaluate("!document.documentElement.hasAttribute('data-gerbang')") and "belum diaktifkan" in pg.inner_text("#admin-pesan"))
    cek("tanpa konfigurasi: tidak ada galat konsol (CSP aktif)", not galat, galat or "")
    ctx.close()

    # ---------- dengan konfigurasi
    ctx, pg, reqs, galat = konteks(b)
    pg.goto(BASE + "/")
    pg.wait_for_url("**/masuk.html*")
    cek("gerbang: pengunjung tanpa sesi dialihkan ke masuk dengan tujuan semula", "lanjut=index.html" in pg.url, pg.url)
    cek("gerbang: pustaka dimuat dari URL yang dipatok", CDN in reqs)
    pg.wait_for_selector("#f-masuk", state="visible")
    cek("klien dibuat dengan PKCE dan sesi tersimpan", pg.evaluate("window.__stub_dipanggil.opsi.auth.flowType === 'pkce' && window.__stub_dipanggil.opsi.auth.persistSession === true && window.__stub_dipanggil.opsi.auth.autoRefreshToken === true"))

    # daftar: validasi
    pg.click('.tabs button[data-tab="daftar"]')
    pg.fill("#f-daftar input[name=email]", "bukan-email"); pg.fill("#f-daftar input[name=sandi]", "rahasia123"); pg.click("#f-daftar button[type=submit]")
    cek("daftar: email tidak valid ditolak di sisi klien", "Format email" in pg.inner_text("#pesan"))
    pg.fill("#f-daftar input[name=email]", "budi@contoh.id"); pg.fill("#f-daftar input[name=sandi]", "pendek"); pg.click("#f-daftar button[type=submit]")
    cek("daftar: kata sandi kurang dari 8 karakter ditolak", "minimal 8" in pg.inner_text("#pesan"))
    pg.fill("#f-daftar input[name=sandi]", "rahasia123"); pg.click("#f-daftar button[type=submit]")
    pg.wait_for_selector("#tampilan-status", state="visible")
    cek("daftar: akun baru langsung berstatus menunggu persetujuan", "Menunggu persetujuan" in pg.inner_text("#status-judul") and pg.evaluate("__stub.profil('budi@contoh.id').status") == "menunggu")
    cek("daftar: tautan konfirmasi mengarah ke masuk.html milik situs ini", pg.evaluate("__stub_redirect") == BASE + "/masuk.html")
    pg.screenshot(path=str(OUT / "auth-status.png"))
    pg.goto(BASE + "/")
    pg.wait_for_url("**/masuk.html*")
    cek("gerbang: akun yang masih menunggu tidak bisa membuka studio", pg.locator("#tampilan-status").is_visible())

    # masuk: sandi salah, sandi benar tetap menunggu
    pg.click("#b-keluar"); pg.wait_for_selector("#f-masuk", state="visible")
    masuk(pg, "budi@contoh.id", "salah-sandi")
    espera(pg, "document.querySelector('#pesan') && !document.querySelector('#pesan').hidden")
    cek("masuk: sandi salah memberi pesan Indonesia", pg.inner_text("#pesan") == "Email atau kata sandi salah.")

    # admin menyetujui
    pg.evaluate("__stub.buat('admin@contoh.id', 'adminrahasia1', {peran:'admin', status:'aktif', aktif_sampai:null})")
    pg.evaluate("__stub.buat('<img/src=x/onerror=window.__xss=1>@jahat.co', 'xss-xss-xss', {})")
    masuk(pg, "admin@contoh.id", "adminrahasia1")
    pg.wait_for_url(BASE + "/index.html")
    pg.wait_for_selector(".gaya")
    cek("masuk admin: dialihkan ke studio, email tampil, tautan Admin terlihat", pg.inner_text("#akun-email") == "admin@contoh.id" and pg.locator("#akun-admin").is_visible())
    pg.screenshot(path=str(OUT / "auth-studio.png"))
    pg.click("#akun-admin")
    pg.wait_for_selector("#admin-baris tr")
    cek("admin: daftar pengguna tampil dengan hitung per status", "Menunggu (2)" in pg.inner_text("#admin-filter"), pg.inner_text("#admin-filter").replace("\n", " "))
    cek("admin: kotak penolakan TIDAK terlihat bagi admin (atribut hidden dihormati)", pg.locator("#admin-tolak").is_hidden() and pg.locator("#admin-isi").is_visible())
    cek("admin: akun menunggu tidak menampilkan masa aktif palsu", "tanpa batas" not in pg.locator("tr", has_text="@jahat.co").inner_text() and "\u2014" in pg.locator("tr", has_text="@jahat.co").inner_text())
    cek("admin: sel tabel tetap sel tabel (tidak diubah menjadi flex)", pg.evaluate("[...document.querySelectorAll('#admin-baris td')].every(td => getComputedStyle(td).display === 'table-cell')"))
    cek("admin: akun sendiri tidak punya tombol tindakan", pg.locator("tr", has_text="admin@contoh.id").locator("button").count() == 0 and "Akunmu sendiri" in pg.inner_text("#admin-baris"))
    cek("XSS: email berisi HTML ditampilkan sebagai teks, tidak dieksekusi", pg.evaluate("window.__xss === undefined") and "<img/src=x" in pg.inner_text("#admin-baris"))
    pg.fill("#admin-cari", "budi")
    baris = pg.locator("tr", has_text="budi@contoh.id")
    baris.locator("select[data-hari]").select_option("90")
    baris.locator('button[data-aksi="aktifkan"]').click()
    pg.wait_for_selector("tr:has-text('budi@contoh.id') .b-aktif")
    prof = pg.evaluate("__stub.profil('budi@contoh.id')")
    from datetime import datetime, timezone
    hari = (datetime.fromisoformat(prof["aktif_sampai"].replace("Z", "+00:00")) - datetime.now(timezone.utc)).total_seconds() / 86400
    cek("admin: mengaktifkan 90 hari menyimpan status dan tanggal yang benar", prof["status"] == "aktif" and 89.9 < hari < 90.1, f"{hari:.2f} hari")
    cek("admin: perubahan tercatat di log audit", "admin@contoh.id" in pg.inner_text("#admin-audit") and "menunggu" in pg.inner_text("#admin-audit"))
    # perpanjangan menyambung
    baris.locator("select[data-hari]").select_option("30")
    baris.locator('button[data-aksi="aktifkan"]').click()
    espera(pg, "__stub.audit().length >= 2")
    prof2 = pg.evaluate("__stub.profil('budi@contoh.id')")
    hari2 = (datetime.fromisoformat(prof2["aktif_sampai"].replace("Z", "+00:00")) - datetime.now(timezone.utc)).total_seconds() / 86400
    cek("admin: perpanjangan 30 hari menyambung dari akhir masa aktif (120 hari)", 119.9 < hari2 < 120.1, f"{hari2:.2f} hari")
    cek("admin: audit perpanjangan dibaca 'diperpanjang', bukan 'aktif -> aktif'", "diperpanjang sampai" in pg.inner_text("#admin-audit"))
    pg.set_viewport_size({"width": 1100, "height": 800}); pg.fill("#admin-cari", "")
    pg.screenshot(path=str(OUT / "auth-admin.png"), full_page=True)

    # user aktif
    pg.click("#akun-keluar"); pg.wait_for_selector("#f-masuk", state="visible")
    masuk(pg, "budi@contoh.id", "rahasia123")
    pg.wait_for_url(BASE + "/index.html")
    pg.wait_for_selector(".gaya")
    cek("user aktif: masuk ke studio, tanpa tautan Admin", pg.inner_text("#akun-email") == "budi@contoh.id" and pg.locator("#akun-admin").is_hidden())
    pg.goto(BASE + "/admin.html")
    pg.wait_for_selector("#admin-tolak", state="visible")
    cek("user biasa: halaman admin menolak dan tidak memuat data", pg.locator("#admin-isi").is_hidden() and pg.locator("#admin-baris tr").count() == 0)

    # kedaluwarsa
    pg.evaluate("__stub.ubah('budi@contoh.id', {aktif_sampai: new Date(Date.now() - 86400000).toISOString()})")
    pg.goto(BASE + "/")
    pg.wait_for_url("**/masuk.html*")
    cek("kedaluwarsa: akses dicabut dan alasannya jelas", "Masa aktif berakhir" in pg.inner_text("#status-judul") and "berakhir pada" in pg.inner_text("#status-isi"), pg.inner_text("#status-isi")[:60])

    # penangguhan oleh admin lewat UI
    pg.click("#b-keluar"); pg.wait_for_selector("#f-masuk", state="visible")
    pg.evaluate("__stub.ubah('budi@contoh.id', {aktif_sampai: new Date(Date.now() + 5*86400000).toISOString()})")
    masuk(pg, "admin@contoh.id", "adminrahasia1"); pg.wait_for_url(BASE + "/index.html")
    pg.goto(BASE + "/admin.html"); pg.wait_for_selector("#admin-baris tr")
    pg.locator("tr", has_text="budi@contoh.id").locator('button[data-aksi="tangguhkan"]').click()
    pg.wait_for_selector("tr:has-text('budi@contoh.id') .b-ditangguhkan")
    pg.click("#akun-keluar"); pg.wait_for_selector("#f-masuk", state="visible")
    masuk(pg, "budi@contoh.id", "rahasia123"); pg.wait_for_selector("#tampilan-status", state="visible")
    cek("penangguhan: user melihat akunnya ditangguhkan dan tidak masuk studio", "ditangguhkan" in pg.inner_text("#status-judul").lower())

    # open redirect
    pg.evaluate("__stub.ubah('budi@contoh.id', {status:'aktif'})")
    pg.click("#b-keluar"); pg.wait_for_selector("#f-masuk", state="visible")
    pg.goto(BASE + "/masuk.html?lanjut=//evil.example/x")
    masuk(pg, "budi@contoh.id", "rahasia123")
    pg.wait_for_url(BASE + "/index.html")
    cek("open redirect: tujuan eksternal diabaikan, mendarat di situs sendiri", pg.url == BASE + "/index.html", pg.url)
    cek("tidak ada galat konsol selama seluruh alur (termasuk pelanggaran CSP)", not galat, galat[:3] or "")
    ctx.close()

    # ---------- konfirmasi email, pendaftaran ganda, lupa sandi, pemulihan
    ctx, pg, reqs, galat = konteks(b)
    pg.goto(BASE + "/masuk.html"); pg.wait_for_selector("#f-masuk", state="visible")
    pg.evaluate("localStorage.setItem('__stub_konfirmasi','1')")
    pg.click('.tabs button[data-tab="daftar"]')
    pg.fill("#f-daftar input[name=email]", "sari@contoh.id"); pg.fill("#f-daftar input[name=sandi]", "rahasia123"); pg.click("#f-daftar button[type=submit]")
    pg.wait_for_selector("#pesan.ok")
    pesan_baru = pg.inner_text("#pesan")
    pg.click('.tabs button[data-tab="daftar"]')
    pg.fill("#f-daftar input[name=email]", "sari@contoh.id"); pg.fill("#f-daftar input[name=sandi]", "rahasia123"); pg.click("#f-daftar button[type=submit]")
    espera(pg, "document.querySelector('#pesan.ok')")
    cek("daftar: jawaban sama untuk email baru dan yang sudah terdaftar (tidak membocorkan)", pg.inner_text("#pesan") == pesan_baru)
    masuk(pg, "sari@contoh.id", "rahasia123")
    espera(pg, "document.querySelector('#pesan') && !document.querySelector('#pesan').hidden && /dikonfirmasi/.test(document.querySelector('#pesan').textContent)")
    cek("masuk: email belum dikonfirmasi memberi petunjuk jelas", "dikonfirmasi" in pg.inner_text("#pesan"))
    pg.click('button[data-tab="lupa"]')
    pg.fill("#f-lupa input[name=email]", "sari@contoh.id"); pg.click("#f-lupa button[type=submit]")
    pg.wait_for_selector("#pesan.ok")
    cek("lupa sandi: permintaan terkirim ke alamat pemulihan milik situs ini", pg.evaluate("__stub.reset()[0].redirectTo") == BASE + "/masuk.html" and "Jika email itu terdaftar" in pg.inner_text("#pesan"))
    pg.evaluate("__stub.konfirmasi('sari@contoh.id')")
    pg.goto(BASE + "/masuk.html?stub_pulih=sari@contoh.id")
    pg.wait_for_selector("#f-pulih", state="visible")
    cek("pemulihan: tautan memunculkan formulir kata sandi baru", "Kata sandi baru" in pg.inner_text("#h-masuk"))
    pg.fill("#f-pulih input[name=sandi]", "pendek"); pg.click("#f-pulih button[type=submit]")
    cek("pemulihan: kata sandi pendek ditolak", "minimal 8" in pg.inner_text("#pesan"))
    pg.fill("#f-pulih input[name=sandi]", "sandibaru123"); pg.click("#f-pulih button[type=submit]")
    pg.wait_for_selector("#tampilan-status", state="visible")
    cek("pemulihan: kata sandi tersimpan, akun menunggu persetujuan", "Menunggu" in pg.inner_text("#status-judul") and pg.evaluate("__stub.profil('sari@contoh.id').status") == "menunggu")
    cek("tidak ada galat konsol pada alur pemulihan", not galat, galat[:3] or "")
    ctx.close()

    # ---------- tampilan ponsel
    ctx, pg, reqs, galat = konteks(b, lebar=390, tinggi=844)
    pg.goto(BASE + "/masuk.html"); pg.wait_for_selector("#f-masuk", state="visible")
    cek("ponsel: halaman masuk tidak bergeser ke samping", not pg.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"))
    pg.screenshot(path=str(OUT / "auth-masuk-ponsel.png"))
    pg.evaluate("__stub.buat('admin@contoh.id', 'adminrahasia1', {peran:'admin', status:'aktif'}); __stub.buat('x@y.id', 'sandi-sandi1', {})")
    masuk(pg, "admin@contoh.id", "adminrahasia1"); pg.wait_for_url(BASE + "/index.html")
    pg.goto(BASE + "/admin.html"); pg.wait_for_selector("#admin-baris tr")
    cek("ponsel: halaman admin tidak bergeser (tabel menggulir di dalam wadahnya)", not pg.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"))
    pg.screenshot(path=str(OUT / "auth-admin-ponsel.png"))
    ctx.close()
    b.close()
srv.shutdown()
print(f"\n{sum(hasil)}/{len(hasil)} lolos")
sys.exit(0 if all(hasil) else 1)

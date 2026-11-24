"""Uji mode server di browser: kunci API, membuat job, kemajuan, unduh, batal, ulangi, unggah gambar.
Supabase diganti stub (tests/stub_supabase.js). Jalankan: python3 tests/uji_server.py"""
import io
import json
import sys
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _server

OUT = ROOT / "tests" / "tangkapan"; OUT.mkdir(exist_ok=True)
STUB = (ROOT / "tests" / "stub_supabase.js").read_text(encoding="utf-8")
CDN = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.119.0"
KONFIG = 'window.BIKINMOTION = { supabaseUrl: "https://stub.supabase.co", kunciPublik: "sb_publishable_stub", pollMs: 300 };'
KUNCI = "AIzaSyUJI-KUNCI-RAHASIA-1234"
srv, BASE = _server.mulai()
hasil = []


def cek(nama, ok, ket=""):
    hasil.append(bool(ok)); print(("LOLOS  " if ok else "GAGAL  ") + nama + (f"  ({ket})" if ket else ""))


def espera(pg, js, batas=8.0):
    akhir = time.time() + batas
    while time.time() < akhir:
        if pg.evaluate(js):
            return True
        time.sleep(0.05)
    raise AssertionError("waktu habis menunggu: " + js)


def konteks(b, config=True, lebar=1100, tinggi=800):
    ctx = b.new_context(viewport={"width": lebar, "height": tinggi}, accept_downloads=True)
    ctx.on("dialog", lambda d: d.accept())
    if config:
        ctx.route("**/konfigurasi.js", lambda r: r.fulfill(status=200, content_type="application/javascript", body=KONFIG))
    ctx.route(CDN, lambda r: r.fulfill(status=200, content_type="application/javascript", body=STUB))
    ctx.route("https://stub.supabase.co/**", lambda r: r.fulfill(status=200, body=b"FAKEMP4" if ".mp4" in r.request.url else Image.new("RGB", (4, 4)).tobytes(),
              headers={"content-type": "video/mp4" if ".mp4" in r.request.url else "image/png", **({"content-disposition": 'attachment; filename="v.mp4"'} if "download=" in r.request.url else {})}))
    pg = ctx.new_page(); galat = []
    pg.on("console", lambda m: galat.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: galat.append("pageerror: " + str(e)))
    return ctx, pg, galat


def masuk(pg, email, sandi):
    pg.goto(BASE + "/masuk.html")
    espera(pg, "document.querySelector('#f-masuk').offsetParent !== null || document.querySelector('#tampilan-status').offsetParent !== null")
    if pg.locator("#tampilan-status").is_visible():      # akun sebelumnya masih masuk: keluar dulu
        pg.click("#b-keluar")
    pg.wait_for_selector("#f-masuk", state="visible")
    pg.fill("#f-masuk input[name=email]", email); pg.fill("#f-masuk input[name=sandi]", sandi); pg.click("#f-masuk button[type=submit]")


def png(n=64):
    b = io.BytesIO(); Image.new("RGB", (n, n), (200, 100, 50)).save(b, "PNG"); return b.getvalue()


with sync_playwright() as p:
    b = p.chromium.launch()

    # ---------- mode lokal (tanpa konfigurasi) tidak berubah
    ctx, pg, galat = konteks(b, config=False)
    pg.goto(BASE + "/"); pg.wait_for_selector(".gaya")
    pg.click('button[data-tambah="gambar"]')
    cek("mode lokal: panel server tersembunyi dan gambar tetap berupa path teks", pg.locator("#panel-server").is_hidden() and pg.locator('input[data-k="file"]').count() == 1 and pg.locator('input[type=file]').count() == 0)
    for hal in ("video.html", "pengaturan.html"):
        pg.goto(BASE + "/" + hal)
        cek(f"mode lokal: {hal} menjelaskan cara mengaktifkan, tidak menggantung", pg.evaluate("!document.documentElement.hasAttribute('data-gerbang')") and "konfigurasi.js" in pg.inner_text("main"))
    cek("mode lokal: tidak ada galat konsol", not galat, galat or "")
    ctx.close()

    # ---------- mode server
    ctx, pg, galat = konteks(b)
    pg.goto(BASE + "/masuk.html"); pg.wait_for_selector("#f-masuk", state="visible")
    pg.evaluate("__stub.buat('tunggu@contoh.id', 'sandi-sandi-1', {})")
    pg.evaluate("__stub.buat('user@contoh.id', 'sandi-sandi-1', {status:'aktif', aktif_sampai:new Date(Date.now()+30*86400000).toISOString()})")
    uid = pg.evaluate("__stub.profil('user@contoh.id').id")

    masuk(pg, "tunggu@contoh.id", "sandi-sandi-1"); pg.wait_for_selector("#tampilan-status", state="visible")
    for hal in ("pengaturan.html", "video.html"):
        pg.goto(BASE + "/" + hal); pg.wait_for_url("**/masuk.html*")
    cek("akun menunggu: pengaturan dan video saya mengalihkan ke halaman status", pg.locator("#tampilan-status").is_visible())

    masuk(pg, "user@contoh.id", "sandi-sandi-1"); pg.wait_for_url(BASE + "/index.html"); pg.wait_for_selector(".gaya")

    # studio tanpa kunci
    pg.wait_for_selector("#panel-server", state="visible")
    espera(pg, "document.querySelector('#server-kunci').textContent.indexOf('Memeriksa') < 0")
    cek("studio: tanpa kunci, tombol Buat video nonaktif dan mengarahkan ke Pengaturan", pg.locator("#b-buat").is_disabled() and pg.locator("#server-kunci a[href='pengaturan.html']").count() == 1)

    # pengaturan kunci
    pg.click("a[href='pengaturan.html']"); pg.wait_for_selector("#f-kunci")
    espera(pg, "document.querySelector('#p-status').textContent.indexOf('Memuat') < 0")
    cek("pengaturan: awalnya belum ada kunci", "Belum ada kunci" in pg.inner_text("#p-status") and pg.locator("#p-hapus").is_hidden())
    pg.fill("#f-kunci input[name=kunci]", "pendek"); pg.click("#p-simpan")
    cek("pengaturan: kunci yang jelas salah ditolak di sisi klien", "tidak valid" in pg.inner_text("#p-pesan"))
    pg.fill("#f-kunci input[name=kunci]", "kunci dengan spasi di dalamnya yang panjang"); pg.click("#p-simpan")
    cek("pengaturan: kunci berspasi ditolak", "tidak valid" in pg.inner_text("#p-pesan"))
    pg.fill("#f-kunci input[name=kunci]", KUNCI); pg.click("#p-simpan")
    espera(pg, "document.querySelector('#p-status').textContent.indexOf('1234') >= 0")
    cek("pengaturan: kunci tersimpan, hanya 4 karakter terakhir yang tampil", "\u2022\u2022\u2022\u20221234" in pg.inner_text("#p-status") and pg.input_value("#f-kunci input[name=kunci]") == "")
    cek("pengaturan: kunci utuh tidak ada di halaman maupun atribut", KUNCI not in pg.content())
    pg.screenshot(path=str(OUT / "server-pengaturan.png"))
    pg.reload(); espera(pg, "document.querySelector('#p-status').textContent.indexOf('1234') >= 0")
    cek("pengaturan: bertahan setelah muat ulang dan tombol hapus muncul", pg.locator("#p-hapus").is_visible())
    pg.click("#p-hapus"); espera(pg, "document.querySelector('#p-status').textContent.indexOf('Belum ada') >= 0")
    cek("pengaturan: hapus kunci mengosongkan penyimpanan", pg.evaluate("__stub.kunci().length") == 0)
    pg.fill("#f-kunci input[name=kunci]", KUNCI); pg.click("#p-simpan"); espera(pg, "document.querySelector('#p-status').textContent.indexOf('1234') >= 0")

    # membuat job dari studio
    pg.goto(BASE + "/"); pg.wait_for_selector(".gaya")
    espera(pg, "!document.querySelector('#b-buat').disabled")
    pg.click("#b-buat")
    cek("studio: naskah kosong tidak dikirim", "Isi naskah dulu" in pg.inner_text("#server-pesan") and pg.evaluate("__stub.jobs().length") == 0)
    contoh = (ROOT / "examples" / "naskah.contoh.json").read_text(encoding="utf-8")
    pg.locator("details.impor summary").click(); pg.fill("#i-teks", contoh); pg.click("#b-impor")
    pg.locator(".bag").nth(1).locator('input[data-k="nilai"]').fill("abc")
    pg.click("#b-buat")
    cek("studio: naskah bermasalah ditolak dengan petunjuk", "Perbaiki dulu" in pg.inner_text("#server-pesan") and pg.evaluate("__stub.jobs().length") == 0, pg.inner_text("#server-pesan")[:80])
    pg.locator(".bag").nth(1).locator('input[data-k="nilai"]').fill("42")
    pg.locator(".bag").nth(0).locator('textarea[data-k="ucapan"]').fill(" ".join(["kata"] * 460))
    pg.click("#b-buat")
    cek("studio: lebih dari 450 kata ditolak sebelum dikirim", "450 kata" in pg.inner_text("#server-pesan") and pg.evaluate("__stub.jobs().length") == 0)
    pg.locator(".bag").nth(0).locator('textarea[data-k="ucapan"]').fill("Ini contoh hook untuk menguji alur otomatis.")
    pg.click("#b-buat"); espera(pg, "__stub.jobs().length === 1")
    j = pg.evaluate("__stub.jobs()[0]")
    cek("studio: job masuk antrian dengan naskah dan style yang benar, milik akun ini", j["status"] == "antri" and j["user_id"] == uid and j["style"] == "bersih-edukasi" and len(j["naskah"]["bagian"]) == 4 and "Lihat kemajuannya" in pg.inner_text("#server-pesan"))
    pg.click("#b-buat"); espera(pg, "__stub.jobs().length === 2")
    pg.click("#b-buat"); espera(pg, "document.querySelector('#server-pesan').textContent.indexOf('Masih ada 2') >= 0")
    cek("studio: batas 2 video aktif ditolak dengan pesan dari server", pg.evaluate("__stub.jobs().length") == 2, pg.inner_text("#server-pesan"))
    pg.screenshot(path=str(OUT / "server-studio.png"))

    # unggah gambar
    pg.click('button[data-tambah="gambar"]')
    kartu = pg.locator(".bag").last
    cek("studio server: field gambar menjadi pemilih berkas", kartu.locator("input[type=file]").count() == 1)
    kartu.locator("input[type=file]").set_input_files({"name": "Foto Liburan (1).PNG", "mimeType": "image/png", "buffer": png()})
    espera(pg, "document.querySelectorAll('.bag').length && [...document.querySelectorAll('[data-status-berkas]')].some(e => e.textContent.indexOf('Terunggah') >= 0)")
    ob = pg.evaluate("__stub.objek()[0]")
    cek("unggah: berkas masuk folder milik akun dan nama dibersihkan", ob["bucket"] == "unggahan" and ob["path"].startswith(uid + "/") and __import__("re").fullmatch(r"[A-Za-z0-9._-]+", ob["path"].split("/", 1)[1]) is not None, ob["path"])
    n = json.loads(pg.inner_text("#r-json"))
    g = [x for x in n["bagian"] if x["tipe"] == "gambar"][0]
    cek("unggah: naskah memakai rujukan unggahan: dan gambar_user terisi", g["file"] == "unggahan:" + ob["path"] and n["gambar_user"] == [g["file"]])
    kartu = pg.locator(".bag").last
    kartu.locator("input[type=file]").set_input_files({"name": "besar.png", "mimeType": "image/png", "buffer": b"0" * (9 * 1024 * 1024)})
    espera(pg, "[...document.querySelectorAll('[data-status-berkas]')].some(e => e.textContent.indexOf('maksimal 8 MB') >= 0)")
    kartu.locator("input[type=file]").set_input_files({"name": "x.txt", "mimeType": "text/plain", "buffer": b"halo"})
    espera(pg, "[...document.querySelectorAll('[data-status-berkas]')].some(e => e.textContent.indexOf('Format harus') >= 0)")
    cek("unggah: berkas terlalu besar dan format salah ditolak, tidak ada objek tambahan", pg.evaluate("__stub.objek().length") == 1)

    # video saya
    pg.goto(BASE + "/video.html"); pg.wait_for_selector(".job")
    cek("video saya: dua job antri tampil", pg.locator(".job").count() == 2 and pg.locator(".job .b-antri").count() == 2)
    ida, idb = pg.evaluate("__stub.jobs().map(j => j.id)")
    pg.evaluate(f"__stub.jobMaju('{ida}', {{status:'berjalan', progres:40, tahap:'Merender video'}})")
    espera(pg, "[...document.querySelectorAll('.job')].some(j => j.querySelector('progress') && j.textContent.indexOf('Merender video') >= 0)")
    cek("video saya: kemajuan diperbarui otomatis tanpa muat ulang", pg.locator(".job progress").first.get_attribute("value") == "40")
    pg.screenshot(path=str(OUT / "server-video-berjalan.png"))
    pg.evaluate(f"__stub.jobMaju('{ida}', {{status:'selesai', progres:100, hasil_path:'{uid}/{ida}.mp4', kontak_path:'{uid}/{ida}-kontak.png', durasi:12.4, pesan:'Sinkron waktu hanya perkiraan dari jeda audio.'}}); __stub.objekHasil('{uid}/{ida}.mp4'); __stub.objekHasil('{uid}/{ida}-kontak.png')")
    espera(pg, "document.querySelector('[data-aksi=unduh]')")
    cek("video saya: selesai menampilkan tombol unduh, durasi, dan catatan", "12 detik" in pg.inner_text("main") and "perkiraan" in pg.inner_text("main"))
    with pg.expect_download() as d:
        pg.click('[data-aksi="unduh"]')
    cek("video saya: unduh lewat tautan bertanda tangan menghasilkan berkas mp4", d.value.suggested_filename.endswith(".mp4") and Path(d.value.path()).read_bytes() == b"FAKEMP4", d.value.suggested_filename)
    with ctx.expect_page() as pop:
        pg.click('[data-aksi="kontak"]')
    cek("video saya: lembar kontak terbuka di tab baru dari tautan bertanda tangan", "/object/sign/hasil/" in pop.value.url)
    pop.value.close()
    pg.locator(".job", has=pg.locator(f'[data-id="{idb}"]')).locator('[data-aksi="batal"]').click()
    espera(pg, "document.querySelector('.b-dibatalkan')")
    pg.locator('[data-aksi="ulang"]').first.click()
    espera(pg, "__stub.jobs().length === 3")
    cek("video saya: batalkan lalu ulangi membuat job baru dari naskah yang sama", pg.evaluate("__stub.jobs()[2].status") == "antri" and pg.evaluate("__stub.jobs()[2].style") == "bersih-edukasi")
    pg.evaluate("__stub.buatJob('user@contoh.id', {status:'gagal', judul:'<img src=x onerror=window.__xss=1>', pesan:'Kunci <b>x</b> salah', dibuat:new Date(Date.now()+1000).toISOString()})")
    pg.click("#v-muat"); espera(pg, "document.querySelectorAll('.job').length === 4")
    cek("video saya: judul dan pesan berisi HTML tampil sebagai teks, tidak dieksekusi", pg.evaluate("window.__xss === undefined") and "<img src=x" in pg.inner_text("#v-daftar") and "<b>x</b>" in pg.inner_text("#v-daftar"))

    # akun lain tidak melihat job dan kunci
    pg.evaluate("__stub.buat('lain@contoh.id', 'sandi-sandi-2', {status:'aktif', aktif_sampai:new Date(Date.now()+86400000).toISOString()})")
    pg.click("#akun-keluar"); pg.wait_for_url("**/masuk.html*")
    masuk(pg, "lain@contoh.id", "sandi-sandi-2"); pg.wait_for_url(BASE + "/index.html")
    pg.goto(BASE + "/video.html"); espera(pg, "!document.querySelector('#v-kosong').hidden")
    cek("isolasi: akun lain tidak melihat video milik akun pertama", pg.locator(".job").count() == 0)
    pg.goto(BASE + "/pengaturan.html"); espera(pg, "document.querySelector('#p-status').textContent.indexOf('Memuat') < 0")
    cek("isolasi: akun lain tidak melihat kunci akun pertama", "Belum ada kunci" in pg.inner_text("#p-status"))
    cek("tidak ada galat konsol di seluruh alur server (termasuk pelanggaran CSP)", not galat, galat[:3] or "")
    ctx.close()

    # ---------- ponsel
    ctx, pg, galat = konteks(b, lebar=390, tinggi=844)
    pg.goto(BASE + "/masuk.html"); pg.wait_for_selector("#f-masuk", state="visible")
    pg.evaluate("__stub.buat('hp@contoh.id', 'sandi-sandi-3', {status:'aktif', aktif_sampai:new Date(Date.now()+86400000).toISOString()}); __stub.buatJob('hp@contoh.id', {status:'berjalan', progres:55, tahap:'Merender video', judul:'Judul yang sangat panjang sekali untuk menguji pembungkusan baris di layar ponsel'})")
    masuk(pg, "hp@contoh.id", "sandi-sandi-3"); pg.wait_for_url(BASE + "/index.html")
    for hal in ("video.html", "pengaturan.html"):
        pg.goto(BASE + "/" + hal); pg.wait_for_selector("main .panel, .job")
        cek(f"ponsel: {hal} tidak bergeser ke samping", not pg.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"))
    pg.goto(BASE + "/video.html"); pg.wait_for_selector(".job"); pg.screenshot(path=str(OUT / "server-video-ponsel.png"))
    ctx.close(); b.close()
srv.shutdown()
print(f"\n{sum(hasil)}/{len(hasil)} lolos")
sys.exit(0 if all(hasil) else 1)

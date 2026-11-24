(function () {
  "use strict";
  var $ = function (s) { return document.querySelector(s); };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); };
  var NAMA = { antri: "Antri", berjalan: "Diproses", selesai: "Selesai", gagal: "Gagal", dibatalkan: "Dibatalkan" };
  var POLL = (window.BIKINMOTION && window.BIKINMOTION.pollMs) || 3000;
  var ctx = null, timer = null, data = [];

  function pesan(t, jenis) { var p = $("#v-pesan"); if (!t) { p.hidden = true; return; } p.hidden = false; p.className = "notif " + (jenis || "info"); p.textContent = t; }
  function waktu(iso) { try { return new Date(iso).toLocaleString("id-ID", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }); } catch (e) { return ""; } }
  function aktif(j) { return j.status === "antri" || j.status === "berjalan"; }

  function kartu(j) {
    var isi = "";
    if (j.status === "antri") isi = '<p class="catatan-kecil">Menunggu giliran diproses...</p>';
    else if (j.status === "berjalan") isi = '<progress max="100" value="' + (+j.progres || 0) + '" aria-label="Kemajuan"></progress><p class="catatan-kecil">' + esc(j.tahap || "Memproses") + " \u2014 " + (+j.progres || 0) + "%</p>";
    else if (j.status === "gagal") isi = '<p class="notif galat">' + esc(j.pesan || "Gagal diproses.") + "</p>";
    else if (j.status === "selesai") {
      isi = j.hasil_path ? '<p class="catatan-kecil">Durasi ' + esc(Math.round(j.durasi || 0)) + " detik.</p>" : '<p class="catatan-kecil">Berkas sudah dihapus otomatis.</p>';
      if (j.pesan && j.hasil_path) isi += '<p class="notif info">' + esc(j.pesan) + "</p>";
    }
    var aksi = "";
    if (j.status === "selesai" && j.hasil_path) aksi += '<button type="button" class="ikon utama-kecil" data-aksi="unduh" data-id="' + esc(j.id) + '">Unduh video</button>';
    if (j.status === "selesai" && j.kontak_path) aksi += '<button type="button" class="ikon" data-aksi="kontak" data-id="' + esc(j.id) + '">Lihat lembar kontak</button>';
    if (j.status === "antri") aksi += '<button type="button" class="ikon hapus" data-aksi="batal" data-id="' + esc(j.id) + '">Batalkan</button>';
    if (j.status === "gagal" || j.status === "dibatalkan") aksi += '<button type="button" class="ikon" data-aksi="ulang" data-id="' + esc(j.id) + '">Ulangi</button>';
    return '<article class="job"><div class="job-kepala"><h2>' + esc(j.judul || "Tanpa judul") + '</h2><span class="badge b-' + esc(j.status) + '">' + esc(NAMA[j.status] || j.status) + "</span></div>" +
      '<p class="catatan-kecil">' + esc(j.style) + " \u00b7 dibuat " + esc(waktu(j.dibuat)) + "</p>" + isi + (aksi ? '<div class="baris-aksi">' + aksi + "</div>" : "") + "</article>";
  }

  function render() {
    $("#v-daftar").innerHTML = data.map(kartu).join("");
    $("#v-kosong").hidden = data.length > 0;
  }

  function muat() {
    clearTimeout(timer);
    return ctx.k.from("job").select("id,status,judul,style,progres,tahap,pesan,hasil_path,kontak_path,durasi,dibuat,selesai")
      .order("dibuat", { ascending: false }).limit(30).then(function (r) {
        if (r.error) throw r.error;
        data = r.data || []; render();
        if (data.some(aktif)) timer = setTimeout(muat, POLL);
      }).catch(function (e) { pesan(Akses.pesanGalat(e), "galat"); });
  }

  function berkas(path, unduh, nama) {
    return ctx.k.storage.from("hasil").createSignedUrl(path, 600, unduh ? { download: nama } : undefined).then(function (r) {
      if (r.error) throw r.error; return r.data.signedUrl;
    });
  }
  function cari(id) { return data.filter(function (j) { return j.id === id; })[0]; }

  document.addEventListener("click", function (e) {
    var t = e.target.closest("button"); if (!t || !ctx) return;
    if (t.id === "v-muat") { pesan(""); return muat(); }
    var j = cari(t.dataset.id); if (!j) return;
    pesan("");
    if (t.dataset.aksi === "unduh") {
      berkas(j.hasil_path, true, (j.judul || "video").replace(/[^A-Za-z0-9._-]+/g, "-") + ".mp4").then(function (u) { location.assign(u); })
        .catch(function (err) { pesan(Akses.pesanGalat(err), "galat"); });
    } else if (t.dataset.aksi === "kontak") {
      berkas(j.kontak_path, false).then(function (u) { window.open(u, "_blank", "noopener"); }).catch(function (err) { pesan(Akses.pesanGalat(err), "galat"); });
    } else if (t.dataset.aksi === "batal") {
      ctx.k.from("job").update({ status: "dibatalkan" }).eq("id", j.id).select("id").then(function (r) {
        if (r.error) throw r.error;
        if (!r.data || !r.data.length) throw new Error("Video ini sudah mulai diproses dan tidak bisa dibatalkan.");
        return muat();
      }).catch(function (err) { pesan(Akses.pesanGalat(err), "galat"); });
    } else if (t.dataset.aksi === "ulang") {
      t.disabled = true;
      ctx.k.from("job").select("naskah,style,judul").eq("id", j.id).single().then(function (r) {
        if (r.error) throw r.error;
        return ctx.k.from("job").insert({ judul: r.data.judul, style: r.data.style, naskah: r.data.naskah }).select("id").single();
      }).then(function (r) { if (r.error) throw r.error; pesan("Video baru masuk antrian.", "ok"); return muat(); })
        .catch(function (err) { pesan(Akses.pesanGalat(err), "galat"); t.disabled = false; });
    }
  });

  if (!Auth.aktif) {
    document.documentElement.removeAttribute("data-gerbang");
    pesan("Login belum diaktifkan, jadi video di server belum tersedia. Isi web/konfigurasi.js (lihat README).", "info");
    $("#v-muat").hidden = true;
    return;
  }
  Auth.gerbang().then(function (hasil) { if (hasil && hasil.k) { ctx = hasil; return muat(); } });
})();

(function () {
  "use strict";
  var $ = function (s) { return document.querySelector(s); };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); };
  var ctx = null;

  function pesan(t, jenis) { var p = $("#p-pesan"); if (!t) { p.hidden = true; return; } p.hidden = false; p.className = "notif " + (jenis || "info"); p.textContent = t; }

  function tampil(row) {
    var ada = !!row;
    $("#p-status").innerHTML = ada ? 'Kunci tersimpan: <strong>\u2022\u2022\u2022\u2022' + esc(row.akhir) + "</strong> (diperbarui " + esc(Akses.tanggal(row.diperbarui)) + ")." :
      "Belum ada kunci tersimpan. Video belum bisa dibuat sebelum kunci diisi.";
    $("#p-simpan").textContent = ada ? "Ganti kunci" : "Simpan kunci";
    $("#p-hapus").hidden = !ada;
  }
  function muat() {
    return ctx.k.from("kunci_api").select("penyedia,akhir,diperbarui").eq("penyedia", "gemini").maybeSingle().then(function (r) {
      if (r.error) throw r.error; tampil(r.data);
    }).catch(function (e) { pesan(Akses.pesanGalat(e), "galat"); });
  }

  $("#f-kunci").addEventListener("submit", function (e) {
    e.preventDefault(); pesan("");
    var f = e.target, nilai = f.elements.kunci.value.trim();
    if (nilai.length < 16 || /\s/.test(nilai)) return pesan("Kunci tidak valid. Salin ulang dari Google AI Studio tanpa spasi.", "galat");
    var tombol = $("#p-simpan"); tombol.disabled = true;
    ctx.k.rpc("simpan_kunci", { p_penyedia: "gemini", p_nilai: nilai }).then(function (r) {
      if (r.error) throw r.error;
      f.reset(); pesan("Kunci tersimpan.", "ok"); return muat();
    }).catch(function (err) { pesan(Akses.pesanGalat(err), "galat"); }).then(function () { tombol.disabled = false; });
  });

  $("#p-hapus").addEventListener("click", function () {
    if (!confirm("Hapus kunci Gemini? Video baru tidak bisa dibuat sampai kamu menyimpan kunci lagi.")) return;
    pesan("");
    ctx.k.rpc("hapus_kunci", { p_penyedia: "gemini" }).then(function (r) {
      if (r.error) throw r.error; pesan("Kunci dihapus.", "ok"); return muat();
    }).catch(function (err) { pesan(Akses.pesanGalat(err), "galat"); });
  });

  if (!Auth.aktif) {
    document.documentElement.removeAttribute("data-gerbang");
    $("#f-kunci").hidden = true; $("#p-status").textContent = "";
    pesan("Login belum diaktifkan, jadi pengaturan akun belum tersedia. Isi web/konfigurasi.js (lihat README).", "info");
    return;
  }
  Auth.gerbang().then(function (hasil) { if (hasil && hasil.k) { ctx = hasil; return muat(); } });
})();

(function () {
  "use strict";
  var $ = function (s) { return document.querySelector(s); };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); };
  var ctx = null, data = [], filter = "semua", cari = "";
  var NAMA = { menunggu: "Menunggu", aktif: "Aktif", kedaluwarsa: "Kedaluwarsa", ditangguhkan: "Ditangguhkan" };

  function pesan(t, jenis) { var p = $("#admin-pesan"); if (!t) { p.hidden = true; return; } p.hidden = false; p.className = "notif " + (jenis || "info"); p.textContent = t; }
  function kode(p) { var a = Akses.statusAkses(p); return a.boleh ? "aktif" : (a.kode === "tanpa-profil" ? "menunggu" : a.kode); }

  /* "tanpa batas" hanya untuk akun aktif tanpa tanggal (admin); akun yang belum diaktifkan tidak punya masa aktif. */
  function masaAktif(p) { return p.aktif_sampai ? Akses.tanggal(p.aktif_sampai) : (p.status === "aktif" ? "tanpa batas" : "\u2014"); }

  function sisaHari(p) {
    if (!p.aktif_sampai) return "";
    var d = Math.ceil((new Date(p.aktif_sampai) - new Date()) / 86400000);
    return d > 0 ? d + " hari lagi" : "lewat " + Math.abs(d) + " hari";
  }

  function render() {
    var hitung = { semua: data.length, menunggu: 0, aktif: 0, kedaluwarsa: 0, ditangguhkan: 0 };
    data.forEach(function (p) { hitung[kode(p)]++; });
    $("#admin-filter").innerHTML = ["semua", "menunggu", "aktif", "kedaluwarsa", "ditangguhkan"].map(function (k) {
      return '<button type="button" data-filter="' + k + '" aria-pressed="' + (filter === k) + '">' + (k === "semua" ? "Semua" : NAMA[k]) + " (" + hitung[k] + ")</button>";
    }).join("");
    var urut = { menunggu: 0, kedaluwarsa: 1, aktif: 2, ditangguhkan: 3 };
    var baris = data.filter(function (p) { return (filter === "semua" || kode(p) === filter) && (!cari || p.email.toLowerCase().indexOf(cari) >= 0); })
      .sort(function (a, b) { return urut[kode(a)] - urut[kode(b)] || new Date(b.dibuat) - new Date(a.dibuat); });
    $("#admin-baris").innerHTML = baris.length ? baris.map(function (p) {
      var k = kode(p), saya = p.id === ctx.p.id;
      var aksi = saya ? '<span class="catatan-kecil">Akunmu sendiri</span>' :
        '<select data-hari aria-label="Durasi untuk ' + esc(p.email) + '"><option value="30">30 hari</option><option value="90">90 hari</option><option value="365">365 hari</option></select>' +
        '<button type="button" class="ikon" data-aksi="aktifkan" data-id="' + esc(p.id) + '">' + (k === "aktif" ? "Perpanjang" : "Aktifkan") + "</button>" +
        (k === "ditangguhkan" ? "" : '<button type="button" class="ikon hapus" data-aksi="tangguhkan" data-id="' + esc(p.id) + '">Tangguhkan</button>');
      return "<tr><td>" + esc(p.email) + (p.peran === "admin" ? ' <span class="badge b-admin">admin</span>' : "") + '</td><td><span class="badge b-' + k + '">' + NAMA[k] + "</span></td><td>" +
        esc(masaAktif(p)) + (sisaHari(p) ? '<br><small class="catatan-kecil">' + sisaHari(p) + "</small>" : "") + "</td><td>" + esc(Akses.tanggal(p.dibuat)) + '</td><td class="aksi"><div class="aksi-isi">' + aksi + "</div></td></tr>";
    }).join("") : '<tr><td colspan="5" class="kosong-sel">Tidak ada pengguna yang cocok.</td></tr>';
  }

  function muatAudit() {
    return ctx.k.from("audit").select("waktu,oleh,target,aksi,sebelum,sesudah").order("waktu", { ascending: false }).limit(10).then(function (r) {
      if (r.error) throw r.error;
      var email = {}; data.forEach(function (p) { email[p.id] = p.email; });
      $("#admin-audit").innerHTML = (r.data || []).map(function (a) {
        var s = a.sebelum || {}, n = a.sesudah || {};
        var perubahan = s.status === "aktif" && n.status === "aktif" ? "diperpanjang sampai " + esc(Akses.tanggal(n.aktif_sampai))
          : esc(s.status) + " &rarr; " + esc(n.status) + (n.aktif_sampai ? " (sampai " + esc(Akses.tanggal(n.aktif_sampai)) + ")" : "");
        return "<li><strong>" + esc(email[a.oleh] || "sistem") + "</strong> mengubah <strong>" + esc(email[a.target] || "akun") + "</strong>: " + perubahan +
          ' <small class="catatan-kecil">' + esc(new Date(a.waktu).toLocaleString("id-ID")) + "</small></li>";
      }).join("") || '<li class="catatan-kecil">Belum ada perubahan.</li>';
    });
  }

  function muat() {
    return ctx.k.from("profil").select("id,email,status,peran,aktif_sampai,dibuat").order("dibuat", { ascending: false }).limit(1000).then(function (r) {
      if (r.error) throw r.error;
      data = r.data || []; render(); return muatAudit();
    }).catch(function (e) { pesan(Akses.pesanGalat(e), "galat"); });
  }

  function ubah(id, isi, ket) {
    pesan("");
    return ctx.k.from("profil").update(isi).eq("id", id).select("id,status,aktif_sampai").then(function (r) {
      if (r.error) throw r.error;
      if (!r.data || !r.data.length) throw new Error("Perubahan ditolak (bukan admin, atau akun tidak ditemukan).");
      pesan(ket, "ok"); return muat();
    }).catch(function (e) { pesan(Akses.pesanGalat(e), "galat"); });
  }

  document.addEventListener("click", function (e) {
    var t = e.target.closest("button"); if (!t || !ctx) return;
    if (t.dataset.filter) { filter = t.dataset.filter; render(); }
    else if (t.id === "admin-muat") muat();
    else if (t.dataset.aksi) {
      var p = data.filter(function (x) { return x.id === t.dataset.id; })[0]; if (!p) return;
      if (t.dataset.aksi === "aktifkan") {
        var hari = +t.parentNode.querySelector("select[data-hari]").value;
        var sampai = Akses.hitungSampai(new Date(), p.status === "aktif" ? p.aktif_sampai : null, hari);
        ubah(p.id, { status: "aktif", aktif_sampai: sampai }, p.email + " aktif sampai " + Akses.tanggal(sampai) + ".");
      } else if (t.dataset.aksi === "tangguhkan") {
        if (confirm("Tangguhkan " + p.email + "? Akses akun ini langsung dihentikan.")) ubah(p.id, { status: "ditangguhkan" }, p.email + " ditangguhkan.");
      }
    }
  });
  $("#admin-cari").addEventListener("input", function (e) { cari = e.target.value.trim().toLowerCase(); render(); });

  if (!Auth.aktif) {
    document.documentElement.removeAttribute("data-gerbang");
    pesan("Login belum diaktifkan, jadi tidak ada pengguna untuk dikelola. Isi web/konfigurasi.js (lihat README).", "info");
    return;
  }
  Auth.gerbang({ wajibAdmin: true }).then(function (hasil) {
    if (!hasil) return;
    if (hasil.bukanAdmin) { $("#admin-tolak").hidden = false; return; }
    ctx = hasil; $("#admin-isi").hidden = false; return muat();
  });
})();

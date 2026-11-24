(function () {
  "use strict";
  var $ = function (s) { return document.querySelector(s); };
  var tujuan = Akses.lanjutAman(new URLSearchParams(location.search).get("lanjut"), "index.html");
  var mode = { pulih: false };

  function pesan(teks, jenis) {
    var p = $("#pesan");
    if (!teks) { p.hidden = true; p.textContent = ""; return; }
    p.hidden = false; p.className = "notif " + (jenis || "galat"); p.textContent = teks;
  }
  function tampil(id) { ["tampilan-form", "tampilan-status", "f-pulih"].forEach(function (x) { $("#" + x).hidden = x !== id; }); }
  function tab(nama) {
    ["masuk", "daftar", "lupa"].forEach(function (n) { $("#f-" + n).hidden = n !== nama; });
    document.querySelectorAll(".tabs button").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.tab === nama)); });
    $("#h-masuk").textContent = { masuk: "Masuk", daftar: "Buat akun", lupa: "Lupa kata sandi" }[nama];
    pesan("");
  }
  function sibuk(form, ya) {
    var b = form.querySelector("button[type=submit]"); if (b) b.disabled = ya;
    form.setAttribute("aria-busy", String(ya));
  }
  function nilai(form, nama) { return form.elements[nama].value; }

  function tampilStatus(a, p) {
    var teks = {
      menunggu: ["Menunggu persetujuan admin", "Akunmu sudah terdaftar. Setelah pembayaran langgananmu terkonfirmasi, admin akan mengaktifkan akun ini. Tekan Periksa lagi setelah itu."],
      ditangguhkan: ["Akunmu ditangguhkan", "Akses akun ini sedang dihentikan. Hubungi admin untuk informasi lebih lanjut."],
      kedaluwarsa: ["Masa aktif berakhir", "Langgananmu berakhir pada " + Akses.tanggal(a.sampai) + ". Perpanjang langganan, lalu hubungi admin agar akunmu diaktifkan lagi."],
      "tanpa-profil": ["Profil akun belum terbentuk", "Keluar lalu masuk lagi. Jika terulang, hubungi admin."]
    }[a.kode];
    $("#h-masuk").textContent = "Status akun";
    $("#status-judul").textContent = teks[0];
    $("#status-isi").textContent = teks[1];
    $("#status-email").textContent = p && p.email ? "Masuk sebagai " + p.email : "";
    tampil("tampilan-status");
  }

  /* Setelah sesi ada: akun aktif -> lanjut ke tujuan; selain itu tampilkan statusnya. */
  function proses() {
    return Auth.klien().then(function (k) {
      return Auth.sesi(k).then(function (s) {
        if (!s) { tampil("tampilan-form"); tab("masuk"); return; }
        if (mode.pulih) return;
        return Auth.profil(k, s.user.id).then(function (p) {
          var a = Akses.statusAkses(p);
          if (a.boleh) { location.replace(tujuan); return; }
          tampilStatus(a, p || { email: s.user.email });
        });
      });
    }).catch(function (e) { pesan(Akses.pesanGalat(e)); });
  }

  /* ---------- formulir ---------- */
  $("#f-masuk").addEventListener("submit", function (e) {
    e.preventDefault(); var f = e.target; pesan("");
    var email = nilai(f, "email").trim(), sandi = nilai(f, "sandi");
    if (!Akses.emailValid(email)) return pesan("Format email tidak valid.");
    if (!sandi) return pesan("Isi kata sandi.");
    sibuk(f, true);
    Auth.klien().then(function (k) { return k.auth.signInWithPassword({ email: email, password: sandi }); })
      .then(function (r) { if (r.error) throw r.error; return proses(); })
      .catch(function (err) { pesan(Akses.pesanGalat(err)); })
      .then(function () { sibuk(f, false); });
  });

  $("#f-daftar").addEventListener("submit", function (e) {
    e.preventDefault(); var f = e.target; pesan("");
    var email = nilai(f, "email").trim(), sandi = nilai(f, "sandi");
    if (!Akses.emailValid(email)) return pesan("Format email tidak valid.");
    if (sandi.length < 8) return pesan("Kata sandi minimal 8 karakter.");
    sibuk(f, true);
    Auth.klien().then(function (k) {
      return k.auth.signUp({ email: email, password: sandi, options: { emailRedirectTo: location.origin + "/masuk.html" } });
    }).then(function (r) {
      if (r.error) throw r.error;
      if (r.data && r.data.session) return proses();   // konfirmasi email dimatikan: langsung masuk, status 'menunggu'
      // Jawaban sengaja sama untuk email baru maupun yang sudah terdaftar (tidak membocorkan siapa yang terdaftar).
      tab("masuk");
      pesan("Pendaftaran diterima. Cek email untuk tautan konfirmasi (jika diminta), lalu masuk dan tunggu persetujuan admin.", "ok");
    }).catch(function (err) { pesan(Akses.pesanGalat(err)); })
      .then(function () { sibuk(f, false); });
  });

  $("#f-lupa").addEventListener("submit", function (e) {
    e.preventDefault(); var f = e.target; pesan("");
    var email = nilai(f, "email").trim();
    if (!Akses.emailValid(email)) return pesan("Format email tidak valid.");
    sibuk(f, true);
    Auth.klien().then(function (k) { return k.auth.resetPasswordForEmail(email, { redirectTo: location.origin + "/masuk.html" }); })
      .then(function (r) {
        if (r.error) throw r.error;
        tab("masuk");
        pesan("Jika email itu terdaftar, tautan pemulihan sudah dikirim. Buka tautannya dari peramban yang sama.", "ok");
      }).catch(function (err) { pesan(Akses.pesanGalat(err)); })
      .then(function () { sibuk(f, false); });
  });

  $("#f-pulih").addEventListener("submit", function (e) {
    e.preventDefault(); var f = e.target; pesan("");
    var sandi = nilai(f, "sandi");
    if (sandi.length < 8) return pesan("Kata sandi minimal 8 karakter.");
    sibuk(f, true);
    Auth.klien().then(function (k) { return k.auth.updateUser({ password: sandi }); })
      .then(function (r) { if (r.error) throw r.error; mode.pulih = false; return proses(); })
      .catch(function (err) { pesan(Akses.pesanGalat(err)); })
      .then(function () { sibuk(f, false); });
  });

  document.addEventListener("click", function (e) {
    var t = e.target.closest("button"); if (!t) return;
    if (t.dataset.tab) tab(t.dataset.tab);
    else if (t.id === "b-cek") { pesan(""); proses(); }
    else if (t.id === "b-keluar") Auth.klien().then(function (k) { return k.auth.signOut(); }).then(function () { tampil("tampilan-form"); tab("masuk"); });
  });
  $("#lihat-sandi").addEventListener("change", function (e) {
    document.querySelectorAll('input[name=sandi]').forEach(function (i) { i.type = e.target.checked ? "text" : "password"; });
  });

  /* ---------- awal ---------- */
  if (!Auth.aktif) {
    $("#tampilan-form").hidden = true;
    pesan("Login belum diaktifkan. Isi supabaseUrl dan kunciPublik di web/konfigurasi.js (lihat README), atau kembali ke beranda.", "info");
    return;
  }
  var h = new URLSearchParams(location.hash.slice(1)), q = new URLSearchParams(location.search);
  var galatTautan = h.get("error_description") || q.get("error_description");
  if (galatTautan) pesan("Tautan tidak bisa dipakai: " + galatTautan.replace(/\+/g, " ") + ". Minta tautan baru, atau masuk dengan kata sandi.");
  Auth.klien().then(function (k) {
    k.auth.onAuthStateChange(function (evt) {
      if (evt === "PASSWORD_RECOVERY") { mode.pulih = true; $("#h-masuk").textContent = "Kata sandi baru"; tampil("f-pulih"); pesan(""); }
    });
    return proses();
  }).catch(function (err) { pesan(Akses.pesanGalat(err)); });
})();

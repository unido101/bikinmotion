/* Lapisan tipis di atas supabase-js. Pustaka dimuat hanya bila konfigurasi diisi (versi dipatok, bukan "@2" bergerak). */
(function () {
  "use strict";
  var cfg = window.BIKINMOTION || {};
  var AKTIF = !!(cfg.supabaseUrl && cfg.kunciPublik);
  var SUMBER = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.119.0";
  var klienP = null;

  function buat() {
    return window.supabase.createClient(cfg.supabaseUrl, cfg.kunciPublik, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true, flowType: "pkce" }
    });
  }
  function klien() {
    if (!AKTIF) return Promise.reject(new Error("Login belum dikonfigurasi"));
    if (klienP) return klienP;
    klienP = new Promise(function (ok, gagal) {
      if (window.supabase && window.supabase.createClient) return ok(buat());
      var s = document.createElement("script");
      s.src = SUMBER; s.async = true;
      s.onload = function () { try { ok(buat()); } catch (e) { gagal(e); } };
      s.onerror = function () { klienP = null; gagal(new Error("Gagal memuat pustaka Supabase (cek koneksi)")); };
      document.head.appendChild(s);
    });
    return klienP;
  }

  /* Profil milik sesi ini; RLS menjamin user hanya melihat barisnya sendiri. */
  function profil(k, idUser) {
    return k.from("profil").select("id,email,status,peran,aktif_sampai").eq("id", idUser).maybeSingle()
      .then(function (r) { if (r.error) throw r.error; return r.data; });
  }
  function sesi(k) { return k.auth.getSession().then(function (r) { if (r.error) throw r.error; return r.data.session; }); }

  function halamanSaatIni() { var p = location.pathname.split("/").pop(); return p || "index.html"; }
  function pindahKeMasuk() { location.replace("masuk.html?lanjut=" + encodeURIComponent(halamanSaatIni())); }
  function lepas() { document.documentElement.removeAttribute("data-gerbang"); }

  function tampilkanAkun(k, p, akses) {
    var kotak = document.getElementById("akun-info"); if (!kotak) return;
    kotak.hidden = false;
    document.getElementById("akun-email").textContent = p.email;
    var admin = document.getElementById("akun-admin"); if (admin) admin.hidden = !akses.admin;
    document.getElementById("akun-keluar").addEventListener("click", function () {
      k.auth.signOut().then(function () { location.replace("masuk.html"); });
    });
  }

  /* Dipanggil oleh halaman yang butuh login. Tanpa konfigurasi: lolos begitu saja (mode tanpa akun). */
  function gerbang(opsi) {
    opsi = opsi || {};
    if (!AKTIF) { lepas(); return Promise.resolve({ mode: "tanpa-login" }); }
    return klien().then(function (k) {
      return sesi(k).then(function (s) {
        if (!s) { pindahKeMasuk(); return null; }
        return profil(k, s.user.id).then(function (p) {
          var a = Akses.statusAkses(p);
          if (!a.boleh) { pindahKeMasuk(); return null; }
          if (opsi.wajibAdmin && !a.admin) { lepas(); return { k: k, p: p, a: a, bukanAdmin: true }; }
          tampilkanAkun(k, p, a); lepas();
          return { k: k, p: p, a: a };
        });
      });
    }).catch(function (e) {
      lepas();
      var m = document.createElement("div");
      m.className = "galat-muat"; m.setAttribute("role", "alert");
      m.textContent = "Akunmu tidak bisa diverifikasi: " + Akses.pesanGalat(e) + " Muat ulang halaman untuk mencoba lagi.";
      document.body.insertBefore(m, document.body.firstChild);
      return null;
    });
  }

  window.Auth = { aktif: AKTIF, cfg: cfg, klien: klien, profil: profil, sesi: sesi, gerbang: gerbang, tampilkanAkun: tampilkanAkun };
})();

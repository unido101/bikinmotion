/* STUB supabase-js untuk uji. Meniru bentuk API yang dipakai halaman (auth + from().select/update) dan aturan RLS di
   supabase/schema.sql. Bukan library asli: uji ini memeriksa kode halaman, bukan perilaku Supabase sebenarnya. */
(function () {
  var DBK = "__stub_db", SK = "__stub_sesi", KONF = "__stub_konfirmasi", RESET = "__stub_reset";
  function ambil(k, d) { try { var v = JSON.parse(localStorage.getItem(k)); return v == null ? d : v; } catch (e) { return d; } }
  function db() { var d = ambil(DBK, null) || {}; ["users", "profil", "audit", "job", "kunci", "objek"].forEach(function (k) { d[k] = d[k] || []; }); return d; }
  function aktifAkun(d, s) { var p = d.profil.filter(function (x) { return x.id === s.user.id; })[0]; return !!p && p.status === "aktif" && (!p.aktif_sampai || new Date(p.aktif_sampai) > new Date()); }
  function err(code, message) { return { data: null, error: { code: code, message: message } }; }
  function simpan(d) { localStorage.setItem(DBK, JSON.stringify(d)); }
  function sesi() { return ambil(SK, null); }
  function id() { return "u-" + Math.random().toString(36).slice(2, 10); }
  function galat(code, message) { return { code: code, message: message, status: 400, name: "AuthApiError" }; }
  var pendengar = [];
  function emit(e, s) { pendengar.forEach(function (f) { try { f(e, s); } catch (x) {} }); }

  function buatProfil(d, u) {
    d.profil.push({ id: u.id, email: u.email, status: "menunggu", peran: "user", aktif_sampai: null, dibuat: new Date().toISOString() });
  }
  window.__stub = {
    buat: function (email, sandi, patch) {   // pembuat akun langsung (melewati validasi), untuk menyiapkan data uji
      var d = db(), u = { id: id(), email: email, password: sandi, konfirmasi: true };
      d.users.push(u); buatProfil(d, u); Object.assign(d.profil[d.profil.length - 1], patch || {}); simpan(d); return u.id;
    },
    ubah: function (email, patch) { var d = db(); Object.assign(d.profil.filter(function (p) { return p.email === email; })[0], patch); simpan(d); },
    konfirmasi: function (email) { var d = db(); d.users.filter(function (u) { return u.email === email; })[0].konfirmasi = true; simpan(d); },
    profil: function (email) { return db().profil.filter(function (p) { return p.email === email; })[0] || null; },
    audit: function () { return db().audit; },
    reset: function () { return ambil(RESET, []); },
    jobs: function () { return db().job; },
    kunci: function () { return db().kunci; },
    objek: function () { return db().objek; },
    jobMaju: function (id, patch) { var d = db(); Object.assign(d.job.filter(function (j) { return j.id === id; })[0], patch); simpan(d); },
    buatJob: function (email, patch) {   // job langsung di basis data (melewati batas), untuk menyiapkan data uji
      var d = db(), u = d.users.filter(function (x) { return x.email === email; })[0];
      var j = Object.assign({ id: "j-" + id(), user_id: u.id, status: "antri", judul: "Uji", style: "bersih-edukasi", naskah: {}, progres: 0, tahap: null, pesan: null, hasil_path: null, kontak_path: null, durasi: null, dibuat: new Date().toISOString(), selesai: null }, patch || {});
      d.job.push(j); simpan(d); return j.id;
    },
    objekHasil: function (path) { var d = db(); d.objek.push({ bucket: "hasil", path: path, size: 7 }); simpan(d); }
  };

  function Q(t) { this.t = t; this.op = "select"; this.f = []; this.ord = null; this.lim = null; this.vals = null; this.one = false; this.ret = false; this.cols = "*"; }
  Q.prototype.select = function (c) { if (this.op === "update" || this.op === "insert") this.ret = true; else this.cols = c || "*"; return this; };
  Q.prototype.update = function (v) { this.op = "update"; this.vals = v; return this; };
  Q.prototype.eq = function (c, v) { this.f.push([c, v]); return this; };
  Q.prototype.order = function (c, o) { this.ord = [c, o && o.ascending === false ? -1 : 1]; return this; };
  Q.prototype.limit = function (n) { this.lim = n; return this; };
  Q.prototype.maybeSingle = function () { this.one = true; return this; };
  Q.prototype.single = function () { this.one = true; this.ketat = true; return this; };
  Q.prototype.insert = function (v) { this.op = "insert"; this.vals = v; return this; };
  Q.prototype.then = function (ok, ko) { var self = this; return new Promise(function (r) { setTimeout(function () { r(self.jalan()); }, 5); }).then(ok, ko); };
  Q.prototype.jalan = function () {
    var d = db(), s = sesi();
    if (!s) return { data: null, error: { code: "42501", message: "permission denied for table " + this.t } };
    if (this.t === "kunci_api" || this.t === "job") return this.jalanBaru(d, s);
    var saya = d.profil.filter(function (p) { return p.id === s.user.id; })[0];
    var admin = !!saya && saya.peran === "admin" && saya.status === "aktif";
    var self = this, tabel = this.t === "profil" ? d.profil : d.audit;
    var terlihat = this.t === "profil" ? (admin ? tabel : tabel.filter(function (p) { return p.id === s.user.id; })) : (admin ? tabel : []);
    var baris = terlihat.filter(function (r) { return self.f.every(function (c) { return r[c[0]] === c[1]; }); });
    if (this.op === "update") {
      if (Object.keys(this.vals).some(function (k) { return k !== "status" && k !== "aktif_sampai"; }))
        return { data: null, error: { code: "42501", message: "permission denied for table profil" } };
      var kena = admin ? baris.filter(function (r) { return r.id !== s.user.id; }) : [];
      kena.forEach(function (r) {
        var sebelum = { status: r.status, aktif_sampai: r.aktif_sampai };
        Object.assign(r, self.vals);
        d.audit.push({ waktu: new Date().toISOString(), oleh: s.user.id, target: r.id, aksi: "ubah_profil", sebelum: sebelum, sesudah: { status: r.status, aktif_sampai: r.aktif_sampai } });
      });
      simpan(d);
      return { data: this.ret ? kena.map(function (r) { return { id: r.id, status: r.status, aktif_sampai: r.aktif_sampai }; }) : null, error: null };
    }
    if (this.ord) { var o = this.ord; baris = baris.slice().sort(function (a, b) { return (a[o[0]] > b[o[0]] ? 1 : a[o[0]] < b[o[0]] ? -1 : 0) * o[1]; }); }
    if (this.lim) baris = baris.slice(0, this.lim);
    return { data: this.one ? (baris[0] || null) : baris, error: null };
  };

  Q.prototype.jalanBaru = function (d, s) {
    var self = this, saya = d.profil.filter(function (p) { return p.id === s.user.id; })[0];
    var admin = !!saya && saya.peran === "admin" && saya.status === "aktif";
    function saring(rows) { return rows.filter(function (r) { return self.f.every(function (c) { return r[c[0]] === c[1]; }); }); }
    function hasil(rows) {
      if (self.ord) { var o = self.ord; rows = rows.slice().sort(function (a, b) { return (a[o[0]] > b[o[0]] ? 1 : a[o[0]] < b[o[0]] ? -1 : 0) * o[1]; }); }
      if (self.lim) rows = rows.slice(0, self.lim);
      if (self.one) { if (!rows[0] && self.ketat) return err("PGRST116", "JSON object requested, multiple (or no) rows returned"); return { data: rows[0] || null, error: null }; }
      return { data: rows, error: null };
    }
    if (this.t === "kunci_api") {
      var k = saring(d.kunci.filter(function (r) { return r.user_id === s.user.id; })).map(function (r) { return { user_id: r.user_id, penyedia: r.penyedia, akhir: r.akhir, diperbarui: r.diperbarui }; });
      return hasil(k);
    }
    var milik = d.job.filter(function (j) { return j.user_id === s.user.id || admin; });
    if (this.op === "insert") {
      if (!aktifAkun(d, s)) return err("42501", 'new row violates row-level security policy for table "job"');
      var v = this.vals;
      if (!v.naskah || typeof v.naskah !== "object" || Array.isArray(v.naskah)) return err("P0001", "Naskah tidak valid.");
      if (d.job.filter(function (j) { return j.user_id === s.user.id && (j.status === "antri" || j.status === "berjalan"); }).length >= 2)
        return err("P0001", "Masih ada 2 video yang diproses. Tunggu salah satunya selesai.");
      var b = { id: "j-" + id(), user_id: s.user.id, status: "antri", judul: String(v.judul || v.naskah.judul || "").slice(0, 120), style: v.style, naskah: v.naskah, progres: 0, tahap: null, pesan: null, hasil_path: null, kontak_path: null, durasi: null, dibuat: new Date().toISOString(), selesai: null };
      d.job.push(b); simpan(d);
      return this.ret ? (this.one ? { data: { id: b.id }, error: null } : { data: [{ id: b.id }], error: null }) : { data: null, error: null };
    }
    if (this.op === "update") {
      if (Object.keys(this.vals).some(function (x) { return x !== "status"; })) return err("42501", "permission denied for table job");
      var kena = saring(milik.filter(function (j) { return j.user_id === s.user.id && j.status === "antri"; }));
      if (kena.length && this.vals.status !== "dibatalkan") return err("42501", "new row violates row-level security policy for table \"job\"");
      kena.forEach(function (j) { j.status = "dibatalkan"; }); simpan(d);
      return { data: this.ret ? kena.map(function (j) { return { id: j.id }; }) : null, error: null };
    }
    return hasil(saring(milik));
  };

  function bukaSesi(u) { var s = { access_token: "tok-" + u.id, user: { id: u.id, email: u.email } }; localStorage.setItem(SK, JSON.stringify(s)); return s; }

  window.supabase = {
    createClient: function (url, kunci, opsi) {
      window.__stub_dipanggil = { url: url, kunci: kunci, opsi: opsi };
      var pulih = new URLSearchParams(location.search).get("stub_pulih");
      var init = new Promise(function (r) {
        setTimeout(function () {
          if (pulih) { var u = db().users.filter(function (x) { return x.email === pulih; })[0]; if (u) { var s = bukaSesi(u); emit("PASSWORD_RECOVERY", s); } }
          r();
        }, 0);
      });
      return {
        auth: {
          signUp: function (a) {
            return init.then(function () {
              var d = db();
              if (!a.password || a.password.length < 6) return { data: { user: null, session: null }, error: galat("weak_password", "Password should be at least 6 characters.") };
              if (d.users.some(function (u) { return u.email === a.email; })) return { data: { user: { id: id() }, session: null }, error: null };   // tidak membocorkan
              var u = { id: id(), email: a.email, password: a.password, konfirmasi: !localStorage.getItem(KONF) };
              d.users.push(u); buatProfil(d, u); simpan(d);
              window.__stub_redirect = a.options && a.options.emailRedirectTo;
              return { data: { user: { id: u.id }, session: u.konfirmasi ? bukaSesi(u) : null }, error: null };
            });
          },
          signInWithPassword: function (a) {
            return init.then(function () {
              var u = db().users.filter(function (x) { return x.email === a.email && x.password === a.password; })[0];
              if (!u) return { data: { session: null, user: null }, error: galat("invalid_credentials", "Invalid login credentials") };
              if (!u.konfirmasi) return { data: { session: null, user: null }, error: galat("email_not_confirmed", "Email not confirmed") };
              var s = bukaSesi(u); emit("SIGNED_IN", s); return { data: { session: s, user: s.user }, error: null };
            });
          },
          getSession: function () { return init.then(function () { return { data: { session: sesi() }, error: null }; }); },
          onAuthStateChange: function (f) { pendengar.push(f); return { data: { subscription: { unsubscribe: function () {} } } }; },
          signOut: function () { return init.then(function () { localStorage.removeItem(SK); emit("SIGNED_OUT", null); return { error: null }; }); },
          resetPasswordForEmail: function (email, o) {
            return init.then(function () { var r = ambil(RESET, []); r.push({ email: email, redirectTo: o && o.redirectTo }); localStorage.setItem(RESET, JSON.stringify(r)); return { data: {}, error: null }; });
          },
          updateUser: function (a) {
            return init.then(function () {
              var s = sesi(); if (!s) return { data: null, error: galat("session_expired", "no session") };
              if (a.password.length < 6) return { data: null, error: galat("weak_password", "weak") };
              var d = db(), u = d.users.filter(function (x) { return x.id === s.user.id; })[0];
              if (u.password === a.password) return { data: null, error: galat("same_password", "same") };
              u.password = a.password; simpan(d); return { data: { user: s.user }, error: null };
            });
          }
        },
        from: function (t) { return new Q(t); },
        rpc: function (nama, a) {
          return init.then(function () {
            var s = sesi(), d = db();
            if (!s) return err("P0001", "Belum masuk.");
            var punya = d.kunci.filter(function (r) { return r.user_id === s.user.id; })[0];
            if (nama === "simpan_kunci") {
              if (!aktifAkun(d, s)) return err("P0001", "Akun belum aktif.");
              var n = String(a.p_nilai || "").trim();
              if (!/^[A-Za-z0-9_.=+\/-]{16,256}$/.test(n)) return err("P0001", "Format kunci tidak valid. Salin ulang kunci dari Google AI Studio.");
              if (punya) { punya.nilai = n; punya.akhir = n.slice(-4); punya.diperbarui = new Date().toISOString(); }
              else d.kunci.push({ user_id: s.user.id, penyedia: "gemini", nilai: n, akhir: n.slice(-4), diperbarui: new Date().toISOString() });
              simpan(d); return { data: n.slice(-4), error: null };
            }
            if (nama === "hapus_kunci") { d.kunci = d.kunci.filter(function (r) { return r.user_id !== s.user.id; }); simpan(d); return { data: null, error: null }; }
            return err("42883", "function " + nama + " does not exist");
          });
        },
        storage: { from: function (bucket) { return {
          upload: function (path, file) {
            return init.then(function () {
              var s = sesi(), d = db();
              if (!s || bucket !== "unggahan" || path.split("/")[0] !== s.user.id || !aktifAkun(d, s)) return err("42501", "new row violates row-level security policy");
              if (file.size > 8 * 1024 * 1024) return err("413", "The object exceeded the maximum allowed size");
              d.objek.push({ bucket: bucket, path: path, size: file.size, tipe: file.type }); simpan(d);
              return { data: { path: path }, error: null };
            });
          },
          createSignedUrl: function (path, exp, opts) {
            return init.then(function () {
              var s = sesi(), d = db();
              var ada = d.objek.some(function (o) { return o.bucket === bucket && o.path === path; });
              if (!s || !ada || path.split("/")[0] !== s.user.id) return err("404", "Object not found");
              return { data: { signedUrl: "https://stub.supabase.co/storage/v1/object/sign/" + bucket + "/" + path + "?token=stub" + (opts && opts.download ? "&download=" + encodeURIComponent(opts.download) : "") }, error: null };
            });
          }
        }; } }
      };
    }
  };
})();

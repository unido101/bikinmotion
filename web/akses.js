/* Logika akses murni (tanpa DOM, tanpa jaringan): status akun, pesan galat, tautan aman, hitung masa aktif.
   Diuji di Node dan di browser. */
(function (akar) {
  "use strict";

  /* profil: baris tabel public.profil (atau null). Return {boleh, kode, ...}. */
  function statusAkses(profil, sekarang) {
    var now = sekarang ? new Date(sekarang) : new Date();
    if (!profil) return { boleh: false, kode: "tanpa-profil" };
    if (profil.status === "ditangguhkan") return { boleh: false, kode: "ditangguhkan" };
    if (profil.status !== "aktif") return { boleh: false, kode: "menunggu" };
    if (profil.aktif_sampai && new Date(profil.aktif_sampai) <= now)
      return { boleh: false, kode: "kedaluwarsa", sampai: profil.aktif_sampai };
    return { boleh: true, kode: "aktif", sampai: profil.aktif_sampai || null, admin: profil.peran === "admin" };
  }

  /* Pesan galat Supabase Auth -> bahasa Indonesia yang jelas. */
  function pesanGalat(err) {
    if (!err) return "";
    var kode = String(err.code || "").toLowerCase(), msg = String(err.message || err);
    // Galat dari basis data: P0001 = pesan buatan kita (sudah berbahasa Indonesia); 42501 = ditolak aturan akses.
    if (kode === "p0001") return msg;
    if (kode === "42501") return "Akunmu belum aktif atau masa aktifnya sudah berakhir, atau aksi ini tidak diizinkan.";
    var peta = {
      invalid_credentials: "Email atau kata sandi salah.",
      user_already_exists: "Email ini sudah terdaftar. Coba masuk.",
      email_exists: "Email ini sudah terdaftar. Coba masuk.",
      email_not_confirmed: "Email belum dikonfirmasi. Cek kotak masuk (dan folder spam), lalu klik tautan konfirmasinya.",
      weak_password: "Kata sandi terlalu lemah. Pakai minimal 8 karakter dengan campuran huruf dan angka.",
      same_password: "Kata sandi baru harus berbeda dari yang lama.",
      signup_disabled: "Pendaftaran sedang ditutup.",
      email_address_invalid: "Format email tidak valid.",
      validation_failed: "Isian tidak valid. Periksa email dan kata sandi.",
      over_email_send_rate_limit: "Terlalu banyak email terkirim. Tunggu beberapa menit lalu coba lagi.",
      over_request_rate_limit: "Terlalu banyak percobaan. Tunggu beberapa menit lalu coba lagi.",
      session_expired: "Sesi berakhir. Masuk lagi."
    };
    if (peta[kode]) return peta[kode];
    if (/invalid login credentials/i.test(msg)) return peta.invalid_credentials;
    if (/already registered/i.test(msg)) return peta.user_already_exists;
    if (/email not confirmed/i.test(msg)) return peta.email_not_confirmed;
    if (/rate limit/i.test(msg)) return peta.over_request_rate_limit;
    if (/failed to fetch|networkerror|load failed|retryable/i.test(msg + " " + (err.name || "")))
      return "Tidak bisa terhubung ke server. Periksa koneksi internet lalu coba lagi.";
    return "Terjadi masalah: " + msg;
  }

  /* Hanya izinkan tujuan pengalihan berupa halaman milik situs ini (cegah open redirect). */
  function lanjutAman(nilai, bawaan) {
    if (typeof nilai === "string" && /^(?:\/|[A-Za-z0-9_-]+(?:\.html)?)(?:[?#][^\s\\]*)?$/.test(nilai)) return nilai;
    return bawaan;
  }

  function emailValid(e) { return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(String(e || "").trim()); }

  /* Masa aktif baru: dihitung dari yang lebih akhir antara sekarang dan masa aktif saat ini (perpanjangan tidak hangus). */
  function hitungSampai(sekarang, aktifSampai, hari) {
    var now = new Date(sekarang), dasar = now;
    if (aktifSampai) { var a = new Date(aktifSampai); if (!isNaN(a) && a > now) dasar = a; }
    return new Date(dasar.getTime() + hari * 86400000).toISOString();
  }

  function tanggal(iso) {
    if (!iso) return "tanpa batas";
    try { return new Date(iso).toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" }); } catch (e) { return String(iso); }
  }

  var api = { statusAkses: statusAkses, pesanGalat: pesanGalat, lanjutAman: lanjutAman, emailValid: emailValid, hitungSampai: hitungSampai, tanggal: tanggal };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else akar.Akses = api;
})(typeof window !== "undefined" ? window : globalThis);

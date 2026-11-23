/* Dimuat di <head> sebelum isi halaman: bila login aktif, sembunyikan halaman sampai akses diverifikasi
   (mencegah kilasan isi halaman sebelum pengalihan). Berkas terpisah agar CSP tidak perlu 'unsafe-inline' untuk skrip. */
(function () {
  var c = window.BIKINMOTION || {};
  if (c.supabaseUrl && c.kunciPublik) document.documentElement.setAttribute("data-gerbang", "");
})();

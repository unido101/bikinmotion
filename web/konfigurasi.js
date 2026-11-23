/* Konfigurasi publik Supabase. Dua nilai ini AMAN dilihat siapa pun (memang dikirim ke browser);
   yang melindungi data adalah Row Level Security di supabase/schema.sql.
   JANGAN PERNAH menaruh kunci "secret" / "service_role" di sini.

   Kosongkan kedua nilai untuk mematikan login (situs berjalan seperti biasa, tanpa akun).

   Project URL dan kunci ada di Supabase > Project Settings > API:
   - supabaseUrl : https://xxxxxxxx.supabase.co
   - kunciPublik : kunci "publishable" (sb_publishable_...) atau "anon" lama */
window.BIKINMOTION = {
  supabaseUrl: "",
  kunciPublik: ""
  // pollMs: 3000   // (opsional) seberapa sering halaman "Video saya" memeriksa kemajuan, dalam milidetik
};

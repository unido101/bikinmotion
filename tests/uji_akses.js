// Uji unit logika akses murni (web/akses.js). Jalankan: node tests/uji_akses.js
const A = require("../web/akses.js");
let gagal = 0;
function cek(nama, ok, ket) { if (!ok) gagal++; console.log((ok ? "LOLOS  " : "GAGAL  ") + nama + (ket ? "  (" + ket + ")" : "")); }
const T = "2026-11-21T00:00:00Z", maju = (h) => new Date(Date.parse(T) + h * 86400000).toISOString();

cek("status: tanpa profil -> ditolak", A.statusAkses(null, T).kode === "tanpa-profil");
cek("status: menunggu", A.statusAkses({ status: "menunggu" }, T).kode === "menunggu");
cek("status: ditangguhkan", A.statusAkses({ status: "ditangguhkan", aktif_sampai: maju(30) }, T).kode === "ditangguhkan");
cek("status: aktif dan belum lewat -> boleh", A.statusAkses({ status: "aktif", aktif_sampai: maju(1) }, T).boleh === true);
cek("status: aktif tapi sudah lewat -> kedaluwarsa", A.statusAkses({ status: "aktif", aktif_sampai: maju(-1) }, T).kode === "kedaluwarsa");
cek("status: tepat pada batas dianggap berakhir", A.statusAkses({ status: "aktif", aktif_sampai: T }, T).kode === "kedaluwarsa");
cek("status: aktif tanpa batas (admin) -> boleh dan admin", (r => r.boleh && r.admin)(A.statusAkses({ status: "aktif", peran: "admin", aktif_sampai: null }, T)));
cek("status: status asing tidak dianggap aktif", A.statusAkses({ status: "AKTIF" }, T).boleh === false);

const hs = A.hitungSampai;
cek("masa aktif: aktivasi baru = sekarang + 30 hari", hs(T, null, 30) === maju(30));
cek("masa aktif: dari yang sudah lewat dihitung dari sekarang", hs(T, maju(-10), 30) === maju(30));
cek("masa aktif: perpanjangan menyambung dari akhir masa aktif (tidak hangus)", hs(T, maju(5), 30) === maju(35));
cek("masa aktif: nilai rusak diabaikan", hs(T, "bukan-tanggal", 7) === maju(7));

const la = A.lanjutAman;
for (const [masuk, harap] of [["index.html", "index.html"], ["admin", "admin"], ["/", "/"], ["index.html?a=1#x", "index.html?a=1#x"],
  ["//evil.example", "B"], ["https://evil.example", "B"], ["javascript:alert(1)", "B"], ["/\\evil.example", "B"], ["\\\\evil", "B"],
  ["../x", "B"], ["a b", "B"], [null, "B"], ["", "B"], ["data:text/html,x", "B"], ["http:evil", "B"]])
  cek(`lanjutAman(${JSON.stringify(masuk)})`, la(masuk, "B") === harap);

const pg = A.pesanGalat;
cek("galat: kode invalid_credentials", /salah/.test(pg({ code: "invalid_credentials", message: "x" })));
cek("galat: pesan 'Invalid login credentials' tanpa kode", /salah/.test(pg({ message: "Invalid login credentials" })));
cek("galat: email belum dikonfirmasi", /dikonfirmasi/.test(pg({ code: "email_not_confirmed" })));
cek("galat: kata sandi lemah", /lemah/.test(pg({ code: "weak_password" })));
cek("galat: batas laju email", /Tunggu/.test(pg({ code: "over_email_send_rate_limit" })));
cek("galat: jaringan putus", /terhubung/.test(pg(new TypeError("Failed to fetch"))));
cek("galat: tak dikenal tetap informatif", /Terjadi masalah: aneh/.test(pg({ message: "aneh" })));

cek("galat DB: pesan buatan (P0001) ditampilkan apa adanya", pg({ code: "P0001", message: "Masih ada 2 video yang diproses." }) === "Masih ada 2 video yang diproses.");
cek("galat DB: ditolak aturan akses (42501) dijelaskan", /belum aktif/.test(pg({ code: "42501", message: "new row violates row-level security policy" })));
cek("emailValid: wajar", A.emailValid("a@b.co") && A.emailValid(" a.b+c@d.id "));
cek("emailValid: salah", !A.emailValid("a@b") && !A.emailValid("a b@c.co") && !A.emailValid("") && !A.emailValid(null));
cek("tanggal: tanpa batas", A.tanggal(null) === "tanpa batas");
console.log(gagal ? `\n${gagal} gagal` : "\nsemua lolos");
process.exit(gagal ? 1 : 0);

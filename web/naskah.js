/* Logika naskah (murni, tanpa DOM). Aturannya sama dengan pipeline/susun.py (cek_naskah).
   Dipakai halaman web dan diuji terhadap versi Python agar keduanya tidak melenceng. */
(function (akar) {
  "use strict";

  var WAJIB = {
    hook: ["teks"], angka: ["nilai", "label"], poin: ["poin"],
    gambar: ["file"], bar: ["data"], penutup: ["teks"], label: ["teks"]
  };
  var PERLU_SUMBER = { angka: true, bar: true };

  /* "Kata *kunci* di sini" -> daftar kata (tanda * tidak dihitung) */
  function bersihkan(ucapan) {
    var hasil = [], sorot = false;
    String(ucapan).split(/\s+/).filter(Boolean).forEach(function (tok) {
      if (tok.charAt(0) === "*") { sorot = true; tok = tok.slice(1); }
      var tutup = tok.slice(-1) === "*";
      var kata = tok.replace(/\*+$/, "");
      if (kata) hasil.push([kata, sorot]);
      if (tutup) sorot = false;
    });
    return hasil;
  }

  function kalimatUcapan(b) {
    var u = b.ucapan;
    var daftar = Array.isArray(u) ? u : [u];
    return daftar.filter(function (x) { return typeof x === "string" && x.trim(); });
  }

  /* Padanan pipeline.susun.cek_naskah. Pesan dibuat identik. */
  function cekNaskah(n, ketat) {
    var galat = [], peringatan = [], bagian = n.bagian || [], totalKata = 0;
    if (!bagian.length) galat.push("naskah tidak punya bagian");
    bagian.forEach(function (b, i) {
      var nama = "bagian " + (i + 1) + " (" + (b.tipe || "?") + ")";
      if (!Object.prototype.hasOwnProperty.call(WAJIB, b.tipe)) {
        galat.push(nama + ": tipe tidak dikenal; pilihan: " + Object.keys(WAJIB).join(", "));
        return;
      }
      WAJIB[b.tipe].forEach(function (k) {
        if (!(k in b)) galat.push(nama + ": field '" + k + "' wajib ada");
      });
      var kal = kalimatUcapan(b);
      if (!kal.length) { galat.push(nama + ": 'ucapan' (teks VO) wajib ada"); return; }
      if (kal.some(function (x) { return x.toLowerCase().indexOf("perlu verifikasi") >= 0; }))
        galat.push(nama + ": ucapan masih bertanda [perlu verifikasi]; verifikasi atau hapus klaimnya");
      kal.forEach(function (x) { totalKata += bersihkan(x).length; });
      if (b.tipe === "poin" && Array.isArray(b.ucapan) && b.ucapan.length !== (b.poin || []).length)
        galat.push(nama + ": jumlah kalimat ucapan (" + b.ucapan.length + ") harus sama dengan jumlah poin (" + (b.poin || []).length + ")");
      if (PERLU_SUMBER[b.tipe] && !b.sumber)
        (ketat ? galat : peringatan).push(nama + ": angka tanpa 'sumber'");
    });
    if (bagian.length && bagian[0].tipe !== "hook") peringatan.push("bagian pertama sebaiknya 'hook'");
    if (bagian.length && bagian[bagian.length - 1].tipe !== "penutup") peringatan.push("bagian terakhir sebaiknya 'penutup'");
    if (totalKata && !(totalKata >= 40 && totalKata <= 180))
      peringatan.push("total " + totalKata + " kata VO (sekitar " + (totalKata / 2.7).toFixed(0) +
        " detik); short form idealnya 40 sampai 180 kata");
    return { galat: galat, peringatan: peringatan, totalKata: totalKata };
  }

  /* ---------- dari isian formulir ke naskah.json ---------- */
  function baris(s) {
    return String(s || "").split("\n").map(function (x) { return x.trim(); }).filter(Boolean);
  }
  function angkaDari(s) {
    var t = String(s == null ? "" : s).trim().replace(",", ".");
    if (t === "" || isNaN(Number(t))) return null;
    return Number(t);
  }
  function satuKalimat(s) { return String(s || "").replace(/\s+/g, " ").trim(); }

  /* Isian wajib yang kosong dihilangkan agar aturan cekNaskah menandainya. */
  function bangunBagian(b, galatUI, nama) {
    var f = b.f || {}, o = { tipe: b.tipe };
    function isi(k, v) { if (v !== "" && v != null && !(Array.isArray(v) && !v.length)) o[k] = v; }
    switch (b.tipe) {
      case "hook":
        isi("teks", baris(f.teks)); isi("label", satuKalimat(f.label));
        if (baris(f.teks).length > 2) galatUI.peringatan.push(nama + ": hook lebih dari 2 baris akan terasa penuh");
        break;
      case "angka": {
        var nilai = angkaDari(f.nilai);
        if (String(f.nilai || "").trim() !== "" && nilai === null) galatUI.galat.push(nama + ": nilai harus berupa angka");
        if (nilai !== null) o.nilai = nilai;
        isi("awalan", f.awalan || ""); isi("akhiran", f.akhiran || "");
        var des = angkaDari(f.desimal); if (des) o.desimal = Math.round(des);
        isi("label", satuKalimat(f.label)); isi("sumber", satuKalimat(f.sumber));
        break;
      }
      case "poin":
        isi("judul", satuKalimat(f.judul)); isi("poin", baris(f.poin));
        break;
      case "bar": {
        isi("judul", satuKalimat(f.judul)); isi("satuan", f.satuan || "");
        var des2 = angkaDari(f.desimal); if (des2) o.desimal = Math.round(des2);
        var data = [];
        baris(f.data).forEach(function (ln) {
          var m = ln.match(/^(.*?)\s*[=:]\s*(-?[\d.,]+)$/), v = m ? angkaDari(m[2]) : null;
          if (!m || v === null) galatUI.galat.push(nama + ": baris data tidak valid: \"" + ln + "\" (tulis: Label = angka)");
          else data.push({ label: m[1], nilai: v });
        });
        if (data.length > 6) galatUI.galat.push(nama + ": grafik maksimal 6 data");
        isi("data", data); isi("sumber", satuKalimat(f.sumber));
        break;
      }
      case "gambar":
        isi("file", satuKalimat(f.file)); isi("teks", satuKalimat(f.teks));
        if (f.bingkai && f.bingkai !== "kartu") o.bingkai = f.bingkai;
        if (f.mode && f.mode !== "auto") o.mode = f.mode;
        if (o.file && !/^(aset\/|unggahan:)/.test(o.file))
          galatUI.peringatan.push(nama + ": taruh gambar di folder aset/ dan tulis path-nya, mis. aset/foto.jpg");
        break;
      case "penutup":
        isi("teks", baris(f.teks)); isi("ajakan", satuKalimat(f.ajakan));
        break;
      case "label":
        isi("teks", satuKalimat(f.teks));
        break;
    }
    if (b.tipe === "poin") isi("ucapan", baris(f.ucapan));
    else isi("ucapan", satuKalimat(f.ucapan));
    return o;
  }

  function bangunNaskah(st) {
    var galatUI = { galat: [], peringatan: [] };
    var n = {};
    if (st.judul && st.judul.trim()) n.judul = st.judul.trim();
    n.style = st.style;
    if (st.voice && st.voice.trim()) n.voice = st.voice.trim();
    if (st.akun && st.akun.trim()) n.akun = st.akun.trim();
    n.bagian = (st.bagian || []).map(function (b, i) {
      return bangunBagian(b, galatUI, "bagian " + (i + 1) + " (" + b.tipe + ")");
    });
    var files = [];
    n.bagian.forEach(function (b) { if (b.tipe === "gambar" && b.file && files.indexOf(b.file) < 0) files.push(b.file); });
    if (files.length) n.gambar_user = files;
    return { naskah: n, ui: galatUI };
  }

  function perkiraanDetik(totalKata) { return totalKata / 2.7; }

  var api = { WAJIB: WAJIB, bersihkan: bersihkan, cekNaskah: cekNaskah, bangunNaskah: bangunNaskah, baris: baris, perkiraanDetik: perkiraanDetik };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else akar.Naskah = api;
})(typeof window !== "undefined" ? window : globalThis);

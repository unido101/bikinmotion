(function () {
  "use strict";
  var KUNCI = "bikinmotion:v1";
  var $ = function (s, a) { return (a || document).querySelector(s); };
  var KATEGORI = { "2d-flat": "2D flat motion", "pixelart": "Pixel art", "3d": "3D motion" };
  var NAMA_TIPE = { hook: "Hook", angka: "Angka", poin: "Poin", bar: "Grafik batang", gambar: "Gambar", label: "Label", penutup: "Penutup" };

  /* Isian per jenis bagian. Contoh di placeholder sengaja netral, bukan fakta. */
  var SKEMA = {
    hook: { bidang: [
      { k: "teks", t: "area", rows: 2, wide: true, label: "Teks di layar", bantu: "Satu baris per baris, maksimal 2. Apit kata penting dengan *bintang*.", ph: "Kalimat pemancing\nKata *penting* disorot" },
      { k: "label", t: "teks", label: "Label stempel (opsional)", ph: "Judul pendek yang mencolok" }],
      ucapan: { label: "Kalimat yang dibacakan", ph: "Satu kalimat pemancing, maksimal tiga detik." } },
    angka: { bidang: [
      { k: "nilai", t: "teks", label: "Angka", bantu: "Boleh pakai koma desimal.", ph: "0" },
      { k: "label", t: "teks", label: "Keterangan di bawah angka", ph: "Apa arti angka ini" },
      { k: "awalan", t: "teks", label: "Awalan (opsional)", ph: "Rp" },
      { k: "akhiran", t: "teks", label: "Akhiran (opsional)", ph: "%" },
      { k: "desimal", t: "teks", label: "Angka di belakang koma", ph: "0" },
      { k: "sumber", t: "teks", label: "Sumber angka", bantu: "Wajib bila angka ini fakta. Tampil kecil di layar.", ph: "Nama lembaga dan tahun" }],
      ucapan: { label: "Kalimat yang dibacakan", ph: "Sebut angkanya dengan kata-kata." } },
    poin: { bidang: [
      { k: "judul", t: "teks", wide: true, label: "Judul daftar (opsional)", ph: "Tiga hal yang perlu diketahui" },
      { k: "poin", t: "area", rows: 3, label: "Poin", bantu: "Satu poin per baris, singkat.", ph: "Poin pertama\nPoin kedua" }],
      ucapan: { t: "area", rows: 3, label: "Kalimat VO per poin", bantu: "Satu kalimat per baris. Jumlahnya harus sama dengan poin, supaya tiap poin muncul tepat saat dibacakan.", ph: "Kalimat untuk poin pertama.\nKalimat untuk poin kedua." } },
    bar: { bidang: [
      { k: "judul", t: "teks", label: "Judul grafik (opsional)", ph: "Perbandingan" },
      { k: "satuan", t: "teks", label: "Satuan (opsional)", ph: " juta" },
      { k: "data", t: "area", rows: 3, wide: true, label: "Data", bantu: "Satu per baris: Label = angka. Maksimal 6.", ph: "Label A = 40\nLabel B = 25" },
      { k: "desimal", t: "teks", label: "Angka di belakang koma", ph: "0" },
      { k: "sumber", t: "teks", label: "Sumber data", bantu: "Wajib bila data ini fakta.", ph: "Nama lembaga dan tahun" }],
      ucapan: { label: "Kalimat yang dibacakan", ph: "Jelaskan apa yang dibandingkan." } },
    gambar: { bidang: [
      { k: "file", t: "teks", label: "Path gambar", bantu: "Taruh berkasnya di folder aset/ pada proyekmu.", ph: "aset/foto.jpg" },
      { k: "teks", t: "teks", label: "Keterangan (opsional)", ph: "Teks di bawah gambar" },
      { k: "bingkai", t: "pilih", label: "Bingkai", opsi: [["kartu", "Kartu (ada ruang di sekitarnya)"], ["penuh", "Penuh layar (ilustrasi latar)"]] },
      { k: "mode", t: "pilih", label: "Pemotongan", opsi: [["auto", "Otomatis"], ["cover", "Isi penuh, dipotong"], ["contain", "Utuh, latar buram"]] }],
      ucapan: { label: "Kalimat yang dibacakan", ph: "Kalimat yang menyertai gambar." } },
    label: { bidang: [
      { k: "teks", t: "teks", wide: true, label: "Teks label", bantu: "Muncul membal bergaya stempel. Singkat saja.", ph: "Plot twist!" }],
      ucapan: { label: "Kalimat yang dibacakan", ph: "Kalimat yang menyertai label." } },
    penutup: { bidang: [
      { k: "teks", t: "area", rows: 2, label: "Teks penutup", bantu: "Satu baris per baris.", ph: "Sampai jumpa" },
      { k: "ajakan", t: "teks", label: "Tombol ajakan (opsional)", ph: "Ikuti untuk lanjutannya" }],
      ucapan: { label: "Kalimat yang dibacakan", ph: "Kesimpulan satu kalimat atau ajakan." } }
  };
  var URUT_TAMBAH = ["hook", "angka", "poin", "bar", "gambar", "label", "penutup"];

  var STYLES = [], filter = "semua";
  var state = muat() || awal();

  function awal() {
    return { style: "bersih-edukasi", judul: "", akun: "", voice: "Kore", os: "win",
      bagian: [{ tipe: "hook", f: {} }, { tipe: "penutup", f: {} }] };
  }
  function muat() {
    try { var s = JSON.parse(localStorage.getItem(KUNCI)); if (s && Array.isArray(s.bagian)) return s; } catch (e) {}
    return null;
  }
  function simpan() { try { localStorage.setItem(KUNCI, JSON.stringify(state)); } catch (e) {} }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function namaStyle(id) { var s = STYLES.filter(function (x) { return x.id === id; })[0]; return s ? s.nama : id; }

  /* ------------------------------------------------ galeri style */
  function renderFilter() {
    var hitung = { semua: STYLES.length };
    STYLES.forEach(function (s) { hitung[s.kategori] = (hitung[s.kategori] || 0) + 1; });
    var tombol = ["semua"].concat(Object.keys(KATEGORI).filter(function (k) { return hitung[k]; }));
    $("#filter").innerHTML = tombol.map(function (k) {
      return '<button type="button" data-filter="' + k + '" aria-pressed="' + (filter === k) + '">' +
        (k === "semua" ? "Semua" : KATEGORI[k]) + " (" + hitung[k] + ")</button>";
    }).join("");
  }
  function renderStyle() {
    var daftar = STYLES.filter(function (s) { return filter === "semua" || s.kategori === filter; });
    $("#daftar-style").innerHTML = daftar.map(function (s) {
      var pakai = s.id === state.style;
      return '<article class="gaya' + (pakai ? " dipakai" : "") + '">' +
        '<div class="info"><h3>' + esc(s.nama) + "</h3><p>" + esc(s.deskripsi) + "</p>" +
        '<div class="sisi"><span class="kategori">' + esc(KATEGORI[s.kategori] || s.kategori) + "</span>" +
        '<span class="palet" aria-hidden="true">' + s.warna.map(function (w) { return '<i style="background:' + esc(w) + '"></i>'; }).join("") + "</span>" +
        '<button type="button" class="pilih" data-pilih="' + esc(s.id) + '" aria-pressed="' + pakai + '">' + (pakai ? "Dipakai" : "Pakai style ini") + "</button></div></div>" +
        '<div class="strip" tabindex="0" role="group" aria-label="Pratinjau style ' + esc(s.nama) + ', geser untuk melihat semua frame">' +
        '<img src="' + esc(s.preview) + '" width="' + s.lebar + '" height="' + s.tinggi + '" loading="lazy" decoding="async" alt="Lima frame contoh style ' + esc(s.nama) + ': hook, angka, poin, grafik, dan penutup"></div></article>';
    }).join("");
    $("#style-dipakai").innerHTML = "Style: <strong>" + esc(namaStyle(state.style)) + '</strong>. <a href="#style">Ganti</a>';
  }

  /* ------------------------------------------------ editor naskah */
  function bidangHtml(i, b, d, nilai) {
    var kelas = d.wide ? ' class="lebar"' : "", bantu = d.bantu ? "<small>" + esc(d.bantu) + "</small>" : "", isi;
    if (d.t === "area") isi = '<textarea data-k="' + d.k + '" rows="' + (d.rows || 2) + '" placeholder="' + esc(d.ph || "") + '">' + esc(nilai) + "</textarea>";
    else if (d.t === "pilih") isi = '<select data-k="' + d.k + '">' + d.opsi.map(function (o) { return '<option value="' + o[0] + '"' + ((nilai || d.opsi[0][0]) === o[0] ? " selected" : "") + ">" + esc(o[1]) + "</option>"; }).join("") + "</select>";
    else isi = '<input type="text" data-k="' + d.k + '" value="' + esc(nilai) + '" placeholder="' + esc(d.ph || "") + '" autocomplete="off">';
    return "<label" + kelas + ">" + esc(d.label) + bantu + isi + "</label>";
  }
  function renderBagian() {
    var host = $("#daftar-bagian");
    if (!state.bagian.length) { host.innerHTML = '<div class="kosong">Belum ada bagian. Mulai dengan hook, lanjutkan dengan isi, dan tutup dengan penutup.</div>'; return; }
    host.innerHTML = state.bagian.map(function (b, i) {
      var sk = SKEMA[b.tipe], f = b.f || {};
      var pilih = '<select data-aksi="tipe" aria-label="Jenis bagian ' + (i + 1) + '">' + Object.keys(NAMA_TIPE).map(function (t) {
        return '<option value="' + t + '"' + (t === b.tipe ? " selected" : "") + ">" + (i + 1) + ". " + NAMA_TIPE[t] + "</option>"; }).join("") + "</select>";
      var uc = sk.ucapan;
      return '<div class="panel bag" data-i="' + i + '"><div class="bag-kepala">' + pilih + '<span class="gap"></span>' +
        '<button type="button" class="ikon" data-aksi="naik"' + (i === 0 ? " disabled" : "") + ' aria-label="Pindah bagian ' + (i + 1) + ' ke atas">Naik</button>' +
        '<button type="button" class="ikon" data-aksi="turun"' + (i === state.bagian.length - 1 ? " disabled" : "") + ' aria-label="Pindah bagian ' + (i + 1) + ' ke bawah">Turun</button>' +
        '<button type="button" class="ikon hapus" data-aksi="hapus" aria-label="Hapus bagian ' + (i + 1) + '">Hapus</button></div>' +
        '<div class="bag-isi">' + sk.bidang.map(function (d) { return bidangHtml(i, b, d, f[d.k]); }).join("") +
        bidangHtml(i, b, { k: "ucapan", t: uc.t || "area", rows: uc.rows || 2, wide: true, label: uc.label, bantu: uc.bantu, ph: uc.ph }, f.ucapan) + "</div></div>";
    }).join("");
  }
  function renderTambah() {
    $("#tambah").innerHTML = URUT_TAMBAH.map(function (t) { return '<button type="button" data-tambah="' + t + '">' + NAMA_TIPE[t] + "</button>"; }).join("");
  }

  /* ------------------------------------------------ ringkasan dan keluaran */
  var jsonTerakhir = "";
  /* Terjemahkan pesan aturan (identik dengan Python) menjadi petunjuk yang menyebut kolom di formulir. */
  function ramah(m) {
    var x = m.match(/^bagian (\d+) \((\w+)\): field '(\w+)' wajib ada$/);
    if (x) {
      var sk = SKEMA[x[2]], d = sk && sk.bidang.filter(function (q) { return q.k === x[3]; })[0];
      return "Bagian " + x[1] + " (" + (NAMA_TIPE[x[2]] || x[2]) + "): isi kolom \u201C" + (d ? d.label : x[3]) + "\u201D.";
    }
    x = m.match(/^bagian (\d+) \((\w+)\): 'ucapan' \(teks VO\) wajib ada$/);
    if (x) return "Bagian " + x[1] + " (" + (NAMA_TIPE[x[2]] || x[2]) + "): isi kalimat yang dibacakan.";
    return m.replace(/^bagian (\d+) \((\w+)\)/, function (_, n, t) { return "Bagian " + n + " (" + (NAMA_TIPE[t] || t) + ")"; });
  }
  function formulirKosong() {
    return !state.bagian.some(function (b) { return Object.keys(b.f || {}).some(function (k) { return String((b.f || {})[k] || "").trim(); }); });
  }
  function perbarui() {
    var h = Naskah.bangunNaskah(state);
    var c = Naskah.cekNaskah(h.naskah, false);
    var galat = h.ui.galat.concat(c.galat), peringatan = h.ui.peringatan.concat(c.peringatan);
    $("#r-kata").textContent = c.totalKata;
    $("#r-durasi").textContent = c.totalKata ? Math.round(Naskah.perkiraanDetik(c.totalKata)) + " dtk" : "0 dtk";
    var li;
    if (formulirKosong()) li = ['<li class="aman">Mulai dari hook: isi teks di layar dan kalimat yang dibacakan, lalu tambahkan bagian isi.</li>'];
    else {
      li = galat.map(function (m) { return '<li class="galat"><strong>Perbaiki:</strong> ' + esc(ramah(m)) + "</li>"; })
        .concat(peringatan.map(function (m) { return '<li class="peringatan"><strong>Periksa:</strong> ' + esc(ramah(m)) + "</li>"; }));
      if (!li.length) li.push('<li class="aman">Naskah siap dijalankan.</li>');
    }
    $("#r-masalah").innerHTML = li.join("");
    jsonTerakhir = JSON.stringify(h.naskah, null, 2);
    $("#r-json").textContent = jsonTerakhir;
  }

  function salin(teks, tombol) {
    var asal = tombol.textContent;
    function ok() { tombol.textContent = "Tersalin"; setTimeout(function () { tombol.textContent = asal; }, 1400); }
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(teks).then(ok, gagal); else gagal();
    function gagal() {
      var t = document.createElement("textarea"); t.value = teks; t.style.position = "fixed"; t.style.opacity = "0";
      document.body.appendChild(t); t.select();
      try { document.execCommand("copy"); ok(); } catch (e) { tombol.textContent = "Salin manual"; }
      document.body.removeChild(t);
    }
  }

  /* ------------------------------------------------ impor */
  function keFormulir(n) {
    var j = function (a) { return Array.isArray(a) ? a.join("\n") : (a == null ? "" : String(a)); };
    var s = function (v) { return v == null ? "" : String(v); };
    return (n.bagian || []).map(function (b) {
      var f = { ucapan: Array.isArray(b.ucapan) ? b.ucapan.join("\n") : s(b.ucapan) };
      switch (b.tipe) {
        case "hook": f.teks = j(b.teks); f.label = s(b.label); break;
        case "angka": f.nilai = s(b.nilai); f.awalan = s(b.awalan); f.akhiran = s(b.akhiran); f.desimal = s(b.desimal); f.label = s(b.label); f.sumber = s(b.sumber); break;
        case "poin": f.judul = s(b.judul); f.poin = j(b.poin); break;
        case "bar": f.judul = s(b.judul); f.satuan = s(b.satuan); f.desimal = s(b.desimal); f.sumber = s(b.sumber);
          f.data = (b.data || []).map(function (d) { return d.label + " = " + d.nilai; }).join("\n"); break;
        case "gambar": f.file = s(b.file); f.teks = s(b.teks); f.bingkai = s(b.bingkai); f.mode = s(b.mode); break;
        case "penutup": f.teks = j(b.teks); f.ajakan = s(b.ajakan); break;
        case "label": f.teks = s(b.teks); break;
      }
      return { tipe: b.tipe, f: f };
    });
  }
  function impor() {
    var pesan = $("#i-pesan"), n;
    try { n = JSON.parse($("#i-teks").value); } catch (e) { pesan.textContent = "Bukan JSON yang valid: " + e.message; return; }
    if (!n || !Array.isArray(n.bagian)) { pesan.textContent = "JSON ini tidak punya daftar \"bagian\"."; return; }
    var asing = n.bagian.filter(function (b) { return !SKEMA[b.tipe]; });
    if (asing.length) { pesan.textContent = "Ada jenis bagian yang tidak dikenal: " + asing.map(function (b) { return b.tipe; }).join(", "); return; }
    state.bagian = keFormulir(n);
    state.judul = n.judul || ""; state.akun = n.akun || ""; state.voice = n.voice || "";
    if (n.style && STYLES.some(function (s) { return s.id === n.style; })) state.style = n.style;
    simpan(); isiUmum(); renderStyle(); renderBagian(); perbarui();
    pesan.textContent = "Termuat: " + state.bagian.length + " bagian.";
  }

  /* ------------------------------------------------ langkah menjalankan */
  function langkah() {
    var w = state.os === "win";
    var L = [
      { j: "Pasang Python dan ffmpeg", p: w ? "Python 3.10 atau lebih baru dari python.org. ffmpeg bisa lewat winget; setelah itu buka terminal baru." : "Python 3.10 atau lebih baru. Pasang ffmpeg lewat pengelola paket, lalu cek hasilnya.",
        k: w ? "winget install Gyan.FFmpeg\nffmpeg -version" : "brew install ffmpeg      # macOS\nsudo apt install ffmpeg # Debian/Ubuntu\nffmpeg -version" },
      { j: "Ambil kodenya", p: "Ganti NAMA-KAMU dengan akun GitHub tempat repo ini kamu simpan.", k: "git clone https://github.com/NAMA-KAMU/bikinmotion\ncd bikinmotion" },
      { j: "Pasang dependensi", p: "faster-whisper bersifat opsional: memberi sinkron per kata. Tanpanya, sinkron diperkirakan dari jeda audio.",
        k: w ? "py -m pip install -r requirements.txt\npy -m pip install faster-whisper" : "python3 -m pip install -r requirements.txt\npython3 -m pip install faster-whisper" },
      { j: "Simpan naskah", p: "Salin naskah.json dari halaman ini ke folder proyek. Gambar yang dipakai taruh di folder aset/ dengan path yang sama seperti di naskah." },
      { j: "Isi kunci Gemini, lalu render", p: "Buat kunci di Google AI Studio. Kunci hanya berlaku di terminal ini. Hasilnya ada di hasil/video.mp4 beserta lembar kontak (.kontak.png) untuk cek visual. Punya rekaman VO sendiri? Tambahkan --audio vo.wav.",
        k: w ? '$env:GEMINI_API_KEY = "kunci-kamu"\npy -m pipeline.otomatis --naskah naskah.json --out hasil\\video.mp4'
             : 'export GEMINI_API_KEY="kunci-kamu"\npython3 -m pipeline.otomatis --naskah naskah.json --out hasil/video.mp4' }
    ];
    $("#langkah").innerHTML = L.map(function (x) {
      return "<li><h3>" + esc(x.j) + "</h3><p>" + esc(x.p) + "</p>" +
        (x.k ? '<div class="kode"><pre>' + esc(x.k) + '</pre><button type="button" data-salin>Salin</button></div>' : "") + "</li>";
    }).join("");
    document.querySelectorAll(".os button").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.os === state.os)); });
  }

  function isiUmum() { $("#f-judul").value = state.judul || ""; $("#f-akun").value = state.akun || ""; $("#f-voice").value = state.voice || ""; }

  /* ------------------------------------------------ peristiwa */
  document.addEventListener("click", function (e) {
    var t = e.target.closest("button"); if (!t) return;
    if (t.dataset.filter) { filter = t.dataset.filter; renderFilter(); renderStyle(); }
    else if (t.dataset.pilih) { state.style = t.dataset.pilih; simpan(); renderStyle(); perbarui(); }
    else if (t.dataset.tambah) {
      state.bagian.push({ tipe: t.dataset.tambah, f: {} }); simpan(); renderBagian(); perbarui();
      var kartu = document.querySelectorAll(".bag"), baru = kartu[kartu.length - 1];
      if (baru) { var fokus = baru.querySelector("textarea, input"); if (fokus) fokus.focus(); }
    } else if (t.dataset.aksi && t.closest(".bag")) {
      var i = +t.closest(".bag").dataset.i, a = t.dataset.aksi;
      if (a === "hapus") state.bagian.splice(i, 1);
      else if (a === "naik" && i > 0) state.bagian.splice(i - 1, 0, state.bagian.splice(i, 1)[0]);
      else if (a === "turun" && i < state.bagian.length - 1) state.bagian.splice(i + 1, 0, state.bagian.splice(i, 1)[0]);
      simpan(); renderBagian(); perbarui();
    } else if (t.id === "b-salin") salin(jsonTerakhir, t);
    else if (t.id === "b-unduh") {
      var a2 = document.createElement("a"); a2.href = URL.createObjectURL(new Blob([jsonTerakhir], { type: "application/json" })); a2.download = "naskah.json";
      document.body.appendChild(a2); a2.click(); document.body.removeChild(a2); setTimeout(function () { URL.revokeObjectURL(a2.href); }, 500);
    } else if (t.id === "b-impor") impor();
    else if (t.id === "b-reset") { if (confirm("Kosongkan formulir? Isian yang belum kamu salin akan hilang.")) { var s0 = state.style, os0 = state.os; state = awal(); state.style = s0; state.os = os0; simpan(); isiUmum(); renderStyle(); renderBagian(); perbarui(); } }
    else if (t.dataset.os) { state.os = t.dataset.os; simpan(); langkah(); }
    else if (t.hasAttribute("data-salin")) salin(t.parentNode.querySelector("pre").textContent, t);
  });
  $("#daftar-bagian").addEventListener("input", function (e) {
    var kartu = e.target.closest(".bag"), k = e.target.dataset.k; if (!kartu || !k) return;
    var b = state.bagian[+kartu.dataset.i]; b.f = b.f || {}; b.f[k] = e.target.value; simpan(); perbarui();
  });
  $("#daftar-bagian").addEventListener("change", function (e) {
    if (e.target.dataset.aksi === "tipe") { state.bagian[+e.target.closest(".bag").dataset.i].tipe = e.target.value; simpan(); renderBagian(); perbarui(); }
  });
  [["#f-judul", "judul"], ["#f-akun", "akun"], ["#f-voice", "voice"]].forEach(function (p) {
    $(p[0]).addEventListener("input", function (e) { state[p[1]] = e.target.value; simpan(); perbarui(); });
  });

  /* ------------------------------------------------ mulai */
  isiUmum(); renderTambah(); renderBagian(); langkah(); perbarui();
  fetch("styles.json").then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }).then(function (d) {
    STYLES = d;
    if (!STYLES.some(function (s) { return s.id === state.style; }) && STYLES.length) state.style = STYLES[0].id;
    renderFilter(); renderStyle(); perbarui();
  }).catch(function (err) {
    $("#daftar-style").innerHTML = '<div class="galat-muat"><strong>Daftar style tidak bisa dimuat</strong> (' + esc(err.message) +
      '). Jika kamu membuka berkas langsung dari folder, jalankan <code>python -m http.server</code> di folder web lalu buka alamat yang ditampilkan.</div>';
  });
})();

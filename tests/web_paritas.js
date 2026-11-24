// Dipanggil oleh tests/uji_web.py: membaca {kasus:[naskah...]} dari stdin, mengeluarkan hasil cekNaskah (biasa dan ketat)
const N = require("../web/naskah.js");
let s = ""; process.stdin.on("data", d => s += d).on("end", () => {
  const { kasus, formulir } = JSON.parse(s);
  const keluar = { kasus: kasus.map(n => ({ biasa: N.cekNaskah(n, false), ketat: N.cekNaskah(n, true) })) };
  keluar.formulir = formulir.map(st => { const r = N.bangunNaskah(st); return { naskah: r.naskah, ui: r.ui }; });
  process.stdout.write(JSON.stringify(keluar));
});

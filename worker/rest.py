"""Klien REST minimal untuk Supabase (PostgREST + Storage) memakai urllib, tanpa dependensi tambahan.

Memakai KUNCI LAYANAN (service role) yang melewati semua aturan akses. Hanya boleh dijalankan di server tepercaya;
jangan pernah ditaruh di browser atau repo.
"""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


class RestGalat(RuntimeError):
    def __init__(self, status, isi):
        super().__init__(f"HTTP {status}: {isi}")
        self.status = status


class BerkasTerlaluBesar(RuntimeError):
    pass


class Rest:
    def __init__(self, url, kunci_layanan, timeout=60):
        self.url = url.rstrip("/")
        self.kunci = kunci_layanan
        self.timeout = timeout

    def _header(self, extra=None):
        h = {"apikey": self.kunci, "Authorization": "Bearer " + self.kunci}
        h.update(extra or {})
        return h

    def _minta(self, metode, jalur, isi=None, header=None, coba=3):
        """Kirim permintaan; ulangi untuk galat jaringan dan 5xx/429. Return (status, byte)."""
        terakhir = None
        for i in range(coba):
            req = urllib.request.Request(self.url + jalur, data=isi, method=metode, headers=self._header(header))
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return r.status, r.read()
            except urllib.error.HTTPError as e:
                badan = e.read().decode("utf-8", "replace")[:200]
                if e.code == 429 or e.code >= 500:
                    terakhir = RestGalat(e.code, badan)
                else:
                    raise RestGalat(e.code, badan)
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                terakhir = RestGalat(0, str(e))
            time.sleep(min(8, 2 ** i))
        raise terakhir

    # ---------------- PostgREST
    def rpc(self, nama, args=None):
        _, b = self._minta("POST", f"/rest/v1/rpc/{nama}", json.dumps(args or {}).encode(), {"Content-Type": "application/json"})
        return json.loads(b) if b else None

    def patch_job(self, id_job, data):
        if not UUID.match(str(id_job)):
            raise ValueError("id job tidak valid")
        self._minta("PATCH", f"/rest/v1/job?id=eq.{id_job}", json.dumps(data).encode(),
                    {"Content-Type": "application/json", "Prefer": "return=minimal"})

    # ---------------- Storage
    @staticmethod
    def _obj(bucket, path):
        return f"/storage/v1/object/{bucket}/{urllib.parse.quote(path, safe='/')}"

    def unduh(self, bucket, path, tujuan, maks_byte):
        """Unduh objek privat ke berkas, dibatasi maks_byte (berhenti sebelum memenuhi disk)."""
        req = urllib.request.Request(self.url + self._obj(bucket, path).replace("/object/", "/object/authenticated/", 1),
                                     headers=self._header())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r, open(tujuan, "wb") as f:
                total = 0
                while True:
                    potong = r.read(65536)
                    if not potong:
                        break
                    total += len(potong)
                    if total > maks_byte:
                        raise BerkasTerlaluBesar(f"lebih dari {maks_byte} byte")
                    f.write(potong)
        except urllib.error.HTTPError as e:
            raise RestGalat(e.code, e.read().decode("utf-8", "replace")[:200])
        return total

    def unggah(self, bucket, path, berkas, content_type):
        with open(berkas, "rb") as f:
            isi = f.read()
        self._minta("POST", self._obj(bucket, path), isi, {"Content-Type": content_type, "x-upsert": "true"})

    def hapus(self, bucket, daftar_path):
        if daftar_path:
            self._minta("DELETE", f"/storage/v1/object/{bucket}", json.dumps({"prefixes": list(daftar_path)}).encode(),
                        {"Content-Type": "application/json"})

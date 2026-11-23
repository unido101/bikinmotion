"""Server uji untuk folder web/: menyajikan berkas dan memasang header yang sama dengan vercel.json
(termasuk Content-Security-Policy), sehingga pelanggaran CSP tampil sebagai galat konsol di uji."""
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def mulai():
    cfg = json.loads((ROOT / "web" / "vercel.json").read_text(encoding="utf-8"))
    global_headers = next(h["headers"] for h in cfg["headers"] if h["source"] == "/(.*)")

    class H(SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def end_headers(self):
            for h in global_headers:
                self.send_header(h["key"], h["value"])
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(H, directory=str(ROOT / "web")))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"

"""HTTP server: REST API + static web dashboard."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from .lens import lens_from_file
from .parser import parse_file

_WEB_DIR = os.path.join(os.path.dirname(__file__), "web")

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
}


class LensHandler(BaseHTTPRequestHandler):
    root: str = "."
    bucket: str = "5min"

    def log_message(self, fmt, *args):
        pass  # silence

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/api/lens":
            bucket = qs.get("bucket", [self.bucket])[0]
            try:
                data = lens_from_file(self.root, bucket=bucket)
            except FileNotFoundError as e:
                return self._json({"error": str(e)}, 404)
            return self._json(data)

        if path == "/api/raw":
            limit = int(qs.get("limit", ["200"])[0])
            entries = parse_file(self.root)[:limit]
            return self._json([{
                "line": e.line_no, "time": e.timestamp.isoformat() if e.timestamp else None,
                "level": e.level, "source": e.source, "message": e.message[:500],
            } for e in entries])

        # static files
        if path == "/":
            path = "/index.html"
        static = os.path.normpath(os.path.join(_WEB_DIR, path.lstrip("/")))
        if not static.startswith(_WEB_DIR) or not os.path.isfile(static):
            self.send_response(404)
            self.end_headers()
            return
        ext = os.path.splitext(static)[1]
        with open(static, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", _CONTENT_TYPES.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(root: str, host: str = "127.0.0.1", port: int = 8765,
          bucket: str = "5min"):
    LensHandler.root = os.path.abspath(root)
    LensHandler.bucket = bucket
    httpd = ThreadingHTTPServer((host, port), LensHandler)
    print(f"LogLens serving {LensHandler.root} at http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()

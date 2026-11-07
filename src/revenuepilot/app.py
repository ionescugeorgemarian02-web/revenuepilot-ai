"""Minimal, dependency-free HTTP shell with one health endpoint."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import json
import os


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/":
            payload = files("revenuepilot").joinpath("index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path != "/health":
            self.send_error(404)
            return
        payload = json.dumps({"status": "ok", "service": "revenuepilot-ai"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        pass


def serve() -> None:
    # Loopback only: this skeleton has no authentication or tenant controls.
    port = int(os.environ.get("REVENUEPILOT_PORT", "8765"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()

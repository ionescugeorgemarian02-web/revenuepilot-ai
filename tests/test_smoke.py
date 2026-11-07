"""Exercise the actual HTTP shell without external network access."""

import json
from pathlib import Path
import sys
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from revenuepilot.app import Handler, ThreadingHTTPServer


class SmokeTest(unittest.TestCase):
    def test_health_and_unknown_route(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            with urlopen(base + "/health", timeout=2) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers["Content-Type"], "application/json; charset=utf-8")
                self.assertEqual(json.load(response), {"status": "ok", "service": "revenuepilot-ai"})
            with self.assertRaises(HTTPError) as error:
                urlopen(base + "/missing", timeout=2)
            self.assertEqual(error.exception.code, 404)
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

"""Run the local Earth-case dashboard: py dashboard.py."""

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from earth_model import CASE_PARAMETERS, DEFAULT_MODULATION, MODULATION_OPTIONS, calculate_earth


WEB_DIRECTORY = Path(__file__).resolve().parent / "web"
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/dashboard.css": ("dashboard.css", "text/css; charset=utf-8"),
    "/dashboard.js": ("dashboard.js", "text/javascript; charset=utf-8"),
}


class DashboardHandler(BaseHTTPRequestHandler):
    def send_body(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status, data):
        self.send_body(status, json.dumps(data, allow_nan=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/config":
            self.send_json(HTTPStatus.OK, {
                "scenario": "Earth",
                "parameters": CASE_PARAMETERS,
                "modulations": MODULATION_OPTIONS,
                "default_modulation": DEFAULT_MODULATION,
            })
        elif path in STATIC_FILES:
            filename, content_type = STATIC_FILES[path]
            self.send_body(HTTPStatus.OK, (WEB_DIRECTORY / filename).read_bytes(), content_type)
        else:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Page not found."})

    def do_POST(self):
        if urlsplit(self.path).path != "/api/calculate":
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Page not found."})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 16384:
                raise ValueError("Send a JSON object smaller than 16 KB.")
            parameters = json.loads(self.rfile.read(size))
            if not isinstance(parameters, dict):
                raise ValueError("Parameters must be a JSON object.")
            result = calculate_earth(parameters)
        except (ValueError, TypeError, OverflowError) as error:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return
        self.send_json(HTTPStatus.OK, result)


def main():
    parser = argparse.ArgumentParser(description="Local spacecraft dashboard (Earth case only).")
    parser.add_argument("--port", type=int, default=8000, help="Local port (default: 8000).")
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), DashboardHandler)
    server.daemon_threads = True
    print(f"Earth dashboard: http://127.0.0.1:{server.server_port}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

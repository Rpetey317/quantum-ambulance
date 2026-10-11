"""Local browser QA harness. Never used by Qollab; submits no remote jobs."""

import argparse
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ambulance import bridge

ROOT = Path(__file__).resolve().parents[1]


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def respond(self, value, code=200):
        raw = json.dumps(value, allow_nan=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            body = ROOT.joinpath("index.html").read_text(encoding="utf-8")
            raw = (
                '<!doctype html><html lang="en"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                "<title>Quantum ambulance · local QA</title>"
                '<link rel="stylesheet" href="/main.css"></head><body>'
                + body
                + '<script type="module" src="/tools/local_ui.js"></script></body></html>'
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(raw)
        elif url.path == "/api/case":
            try:
                self.respond(json.loads(bridge.case_data(parse_qs(url.query)["id"][0])))
            except (ValueError, KeyError) as error:
                self.respond({"error": str(error)}, 400)
        else:
            super().do_GET()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 2_000_000:
                raise ValueError("Payload too large")
            data = json.loads(self.rfile.read(length))
            if self.path == "/api/preview":
                self.respond(json.loads(bridge.preview(json.dumps(data))))
            elif self.path == "/api/quantum":
                from qiskit.providers.basic_provider import BasicSimulator

                self.respond(
                    json.loads(
                        bridge.run_quantum(
                            json.dumps(data["data"]),
                            BasicSimulator(seed_simulator=11),
                            shots=data["shots"],
                        )
                    )
                )
            else:
                self.respond({"error": "Unknown local test route"}, 404)
        except Exception as error:
            self.respond({"error": str(error)}, 400)


def serve(port=8765):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Local QA only: http://127.0.0.1:{server.server_port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    serve(parser.parse_args().port)

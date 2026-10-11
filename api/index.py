"""Vercel Python function: a single public adapter for classical and local QAOA."""

import json
import logging
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from ambulance.web import MAX_BODY_BYTES, backend_info, evaluate_request


class handler(BaseHTTPRequestHandler):
    def respond(self, value, code=200):
        raw = json.dumps(value, allow_nan=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self.respond(backend_info())

    def do_POST(self):
        try:
            if self.headers.get_content_type() != "application/json":
                self.respond({"error": "Use application/json."}, 415)
                return
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY_BYTES:
                self.respond({"error": "Request body must be between 1 byte and 2 MB."}, 413)
                return
            origin = self.headers.get("Origin")
            if origin and urlparse(origin).netloc != self.headers.get("Host"):
                self.respond({"error": "Use the app on this origin to run a case."}, 403)
                return
            payload = json.loads(self.rfile.read(length))
            action = parse_qs(urlparse(self.path).query).get("action", [""])[0]
            self.respond(evaluate_request(action, payload))
        except BlockingIOError as error:
            self.respond({"error": str(error)}, 429)
        except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as error:
            self.respond({"error": str(error)}, 400)
        except Exception:
            logging.exception("Web case evaluation failed")
            self.respond({"error": "The simulator could not complete this run. Please try again later."}, 500)

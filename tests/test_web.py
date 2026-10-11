"""Public transport limits and an actual local simulator job (never IonQ)."""

import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from api.index import handler
from ambulance.core import load_case
from ambulance.web import QUANTUM_SLOT, evaluate_request


class WebTests(unittest.TestCase):
    def test_public_preview_uses_shared_union_and_revision(self):
        case = load_case()
        result = evaluate_request("preview", case)
        self.assertEqual(result["greedy"]["selected_site_indices"], [2, 5, 6])
        self.assertEqual(result["exact"]["covered_weight"], 2086)
        case["k"] = 2
        case["meta"]["revision"] = "web-edit"
        edited = evaluate_request("preview", case)
        self.assertEqual(edited["case_revision"], "web-edit")
        self.assertNotEqual(edited["input_fingerprint"], result["input_fingerprint"])

    def test_public_resource_bounds_reject_before_quantum_import(self):
        for shots in (0, 129, True, 1.5, "64"):
            with self.subTest(shots=shots), self.assertRaises(ValueError):
                evaluate_request("quantum", {"data": load_case(), "shots": shots})
        case = load_case()
        case["sites"].append({"id": "extra", "x_km": 50, "y_km": 50})
        self.assertEqual(evaluate_request("preview", case)["greedy"]["status"], "ok")
        with self.assertRaisesRegex(ValueError, "up to 8"):
            evaluate_request("quantum", {"data": case, "shots": 8})
        case["zones"] *= 300
        with self.assertRaisesRegex(ValueError, "4000 zones"):
            evaluate_request("preview", case)
        for value in (None, [], {}, {"sites": [None], "zones": [None]}):
            with self.assertRaises((ValueError, TypeError)):
                evaluate_request("preview", value)

    def test_busy_instance_submits_nothing(self):
        QUANTUM_SLOT.acquire()
        try:
            with self.assertRaises(BlockingIOError):
                evaluate_request("quantum", {"data": load_case(), "shots": 8})
        finally:
            QUANTUM_SLOT.release()

    def test_actual_public_sampler_job_returns_shared_contract(self):
        try:
            from qiskit.providers.basic_provider import BasicSimulator
        except ImportError:
            self.skipTest("Qiskit not installed")
        case = load_case()
        case["sites"] = case["sites"][:3]
        case["k"] = 2
        case["meta"]["revision"] = "web-quantum"
        original_run = BasicSimulator.run
        calls = []

        def counted(backend, *args, **kwargs):
            calls.append(kwargs["shots"])
            return original_run(backend, *args, **kwargs)

        with patch.object(BasicSimulator, "run", counted):
            result = evaluate_request("quantum", {"data": case, "shots": 8})
        q = result["qaoa"]
        self.assertEqual(calls, [8])
        self.assertEqual(q["status"], "ok")
        self.assertEqual(q["case_revision"], "web-quantum")
        self.assertEqual(q["input_fingerprint"], result["input_fingerprint"])
        self.assertEqual(q["valid_shots"], 8)
        self.assertEqual(len(q["selected_site_ids"]), 2)
        self.assertTrue(q["backend"]["is_simulator"])
        self.assertIsNotNone(q["timings"]["local_optimization_s"])
        self.assertIsNotNone(q["timings"]["backend_job_s"])

    def test_http_errors_limits_and_backend_identity(self):
        class Quiet(handler):
            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Quiet)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def request(method, url, raw=None, headers=None):
            connection = http.client.HTTPConnection(*server.server_address)
            connection.request(method, url, raw, headers or {})
            response = connection.getresponse()
            status, data = response.status, json.loads(response.read())
            connection.close()
            return status, data

        try:
            status, data = request("GET", "/api")
            self.assertEqual(status, 200)
            self.assertEqual(data["shot_cap"], 128)
            self.assertTrue(data["is_simulator"])
            headers = {"Content-Type": "application/json"}
            self.assertEqual(request("POST", "/api?action=preview", "{", headers)[0], 400)
            self.assertEqual(request("POST", "/api?action=preview", "{}", {})[0], 415)
            self.assertEqual(request("POST", "/api?action=unknown", "{}", headers)[0], 400)
            self.assertEqual(request("POST", "/api", "{}", {**headers, "Origin": "https://other.example"})[0], 403)
            self.assertEqual(request("POST", "/api", "x" * 2_000_001, headers)[0], 413)
            status, data = request("POST", "/api?action=preview", json.dumps(load_case()), headers)
            self.assertEqual(status, 200)
            self.assertEqual(data["exact"]["covered_weight"], 2086)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

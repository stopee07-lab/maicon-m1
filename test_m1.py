import contextlib
import io
import json
from pathlib import Path
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.error import HTTPError
from unittest.mock import patch

from m1 import API, Claude, M1Error, Rehearsal, read_order_file, validate_report


EXAMPLE = Path(__file__).with_name("example_order.json")
REPORT = {"target": "RED_RADAR", "search_sectors": ["CM", "R-S1"], "base": "RED_SUPPLY_DEPOT"}
MODEL = "claude-test-local"


class StubResponse(io.BytesIO):
    headers = {"request-id": "req_mock"}


class StubClaude:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        if isinstance(self.response, Exception):
            raise self.response
        return StubResponse(json.dumps(self.response).encode("utf-8"))


class TestM1(unittest.TestCase):
    def test_claude_contract(self):
        claude = Claude("dummy-key")
        claude.opener = StubClaude({
            "stop_reason": "end_turn", "content": [{"type": "text", "text": json.dumps(REPORT)}],
        })
        command = read_order_file(EXAMPLE)
        with contextlib.redirect_stderr(io.StringIO()) as log:
            self.assertEqual(claude.interpret(MODEL, "BLUE", command), REPORT)
        request, = claude.opener.requests
        self.assertEqual((request.get_method(), request.full_url), ("POST", f"{API}/messages"))
        self.assertEqual(request.get_header("X-api-key"), "dummy-key")
        payload = json.loads(request.data)
        self.assertEqual(json.loads(payload["messages"][0]["content"]),
                         {"own_camp": "BLUE", "tactical_command": command})
        self.assertEqual(set(payload["output_config"]["format"]["schema"]["required"]), set(REPORT))
        self.assertNotIn("dummy-key", log.getvalue())

    def test_model_list_is_get_without_text(self):
        claude = Claude("dummy-key")
        claude.opener = StubClaude({"data": [{"id": MODEL}], "has_more": False})
        self.assertEqual(claude.models(), {"models": [MODEL], "has_more": False})
        request, = claude.opener.requests
        self.assertEqual((request.get_method(), request.full_url, request.data), ("GET", f"{API}/models", None))

    def test_model_refusal_and_truncation_are_errors(self):
        claude = Claude("dummy-key")
        for reason in ("refusal", "max_tokens"):
            with self.subTest(reason=reason):
                claude.opener = StubClaude({"stop_reason": reason})
                with self.assertRaises(M1Error):
                    claude.interpret(MODEL, "BLUE", read_order_file(EXAMPLE))
                self.assertEqual(len(claude.opener.requests), 1)

    def test_invalid_report_rejected(self):
        for report in ({**REPORT, "target": None}, {**REPORT, "target": "OTHER"},
                       {**REPORT, "search_sectors": []}, {**REPORT, "search_sectors": ["CM", "CM"]},
                       {**REPORT, "search_sectors": [3]}, {**REPORT, "extra": "no"}):
            with self.subTest(report=report), self.assertRaises(M1Error):
                validate_report(report)

    def test_401_reports_status_without_error_body(self):
        claude = Claude("dummy-key")
        claude.opener = StubClaude(HTTPError(f"{API}/models", 401, "dummy-key", {}, io.BytesIO(b"dummy-key")))
        with self.assertRaisesRegex(M1Error, "HTTP 401") as result:
            claude.models()
        self.assertNotIn("dummy-key", str(result.exception))

    def test_rehearsal_http_flow_and_ack(self):
        requests = []
        command = read_order_file(EXAMPLE)
        phase = "ready"

        class Server(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def reply(self, content):
                data = json.dumps(content).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                requests.append((self.path, self.headers.get("x-api-key")))
                if self.path.startswith("/api/report/me?"):
                    self.reply({"phase": phase, "camp": "BLUE"})
                else:
                    self.reply({"accepted": True, "order": {"tactical_command": command}})

            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append((self.path, self.headers.get("x-api-key"), data))
                if self.path == "/api/report/ready":
                    self.reply({"accepted": True})
                else:
                    self.reply({"accepted": True, "received": {**REPORT, "search_sectors": ["R-S1", "CM"]}})

        with HTTPServer(("127.0.0.1", 0), Server) as server:
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                with patch("m1.TEST_PORT", server.server_port):
                    rehearsal = Rehearsal(f"http://127.0.0.1:{server.server_port}", "dummy-code")
                    self.assertEqual(rehearsal.ready(), {"accepted": True})
                    phase = "running"
                    self.assertEqual(rehearsal.read_order(), ("BLUE", command))
                    self.assertEqual(rehearsal.submit(REPORT), {"accepted": True, "received": REPORT})
            finally:
                server.shutdown()
                thread.join()
        self.assertEqual(requests, [
            ("/api/report/me?mission_code=dummy-code", None),
            ("/api/report/ready", None, {"mission_code": "dummy-code"}),
            ("/api/report/me?mission_code=dummy-code", None),
            ("/api/report/order?mission_code=dummy-code", None),
            ("/api/report/interpretation", None, {"mission_code": "dummy-code", **REPORT}),
        ])

    def test_rehearsal_rejects_main_match_port(self):
        with self.assertRaises(M1Error):
            Rehearsal("http://127.0.0.1:8000", "dummy-code")


if __name__ == "__main__":
    unittest.main()

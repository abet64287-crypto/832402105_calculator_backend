import http.client
import json
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path

from src.controller import create_server


class CalculatorApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "history.db"
        self._start_server()

    def tearDown(self):
        self._stop_server()
        self.temporary_directory.cleanup()

    def _start_server(self):
        self.server = create_server("127.0.0.1", 0, str(self.database_path), "http://localhost:3000")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def _stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            payload = json.dumps(body) if body is not None else None
            request_headers = {"Content-Type": "application/json", "Origin": "http://localhost:3000"}
            request_headers.update(headers or {})
            connection.request(method, path, payload, request_headers)
            response = connection.getresponse()
            content = response.read()
            return response.status, dict(response.getheaders()), json.loads(content) if content else None
        finally:
            connection.close()

    def test_success_history_persistence_and_delete(self):
        status, headers, result = self.request("POST", "/api/calculate", {"expression": "0.1+0.2"})
        self.assertEqual(status, 200)
        self.assertEqual(result["id"], 1)  # The startup write probe must be rolled back.
        self.assertEqual(headers["Access-Control-Allow-Origin"], "http://localhost:3000")
        self.assertEqual(result["result"], 0.3)
        self.assertEqual(result["result_text"], "0.3")
        self.assertEqual(result["expression"], "0.1+0.2")
        self.assertIsInstance(result["id"], int)
        self.assertTrue(result["created_at"])

        record_id = result["id"]
        self._stop_server()
        self._start_server()
        status, _, history = self.request("GET", "/api/history")
        self.assertEqual(status, 200)
        expected_record = {key: result[key] for key in ("id", "expression", "result", "result_text", "created_at")}
        self.assertEqual(history["history"], [expected_record])

        with closing(sqlite3.connect(self.database_path)) as connection:
            stored = connection.execute("SELECT expression, result, created_at FROM calculation_history WHERE id = ?", (record_id,)).fetchone()
        self.assertEqual(stored[0:2], ("0.1+0.2", "0.3"))
        self.assertTrue(stored[2])

        status, _, deleted = self.request("DELETE", f"/api/history/{record_id}")
        self.assertEqual(status, 200)
        self.assertEqual(deleted, {"success": True, "id": record_id})
        status, _, history = self.request("GET", "/api/history")
        self.assertEqual(history["history"], [])
        status, _, error = self.request("DELETE", f"/api/history/{record_id}")
        self.assertEqual(status, 404)
        self.assertEqual(error["error"]["code"], "RECORD_NOT_FOUND")

    def test_errors_do_not_create_history(self):
        for expression, code in [("1+", "INVALID_EXPRESSION"), ("1/(2-2)", "DIVISION_BY_ZERO")]:
            with self.subTest(expression=expression):
                status, _, response = self.request("POST", "/api/calculate", {"expression": expression})
                self.assertEqual(status, 400)
                self.assertEqual(response["success"], False)
                self.assertEqual(response["error"]["code"], code)
        _, _, history = self.request("GET", "/api/history")
        self.assertEqual(history["history"], [])

    def test_exact_result_text_survives_database_restart(self):
        cases = [
            ("1.234567890123456789+0", "1.234567890123456789"),
            ("9007199254740993+0", "9007199254740993"),
        ]
        records = []
        for expression, exact in cases:
            status, _, response = self.request("POST", "/api/calculate", {"expression": expression})
            self.assertEqual(status, 200)
            self.assertEqual(response["result_text"], exact)
            records.append(response)

        self._stop_server()
        self._start_server()
        status, _, response = self.request("GET", "/api/history")
        self.assertEqual(status, 200)
        expected_history = [{key: value for key, value in record.items() if key != "success"} for record in reversed(records)]
        self.assertEqual(response["history"], expected_history)

        with closing(sqlite3.connect(self.database_path)) as connection:
            stored = connection.execute("SELECT result FROM calculation_history ORDER BY id").fetchall()
        self.assertEqual([row[0] for row in stored], [exact for _, exact in cases])

    def test_preflight_and_invalid_request(self):
        status, headers, _ = self.request("OPTIONS", "/api/calculate")
        self.assertEqual(status, 204)
        self.assertIn("POST", headers["Access-Control-Allow-Methods"])
        self.assertEqual(headers["Access-Control-Allow-Origin"], "http://localhost:3000")

        status, _, response = self.request("POST", "/api/calculate", {"expression": 12})
        self.assertEqual(status, 400)
        self.assertEqual(response["error"]["code"], "INVALID_EXPRESSION")

        status, _, response = self.request("DELETE", "/api/history/nope")
        self.assertEqual(status, 400)
        self.assertEqual(response["error"]["code"], "INVALID_ID")

        status, _, response = self.request("DELETE", "/api/history/" + "9" * 4301)
        self.assertEqual(status, 400)
        self.assertEqual(response["error"]["code"], "INVALID_ID")

        status, _, response = self.request("DELETE", "/api/history/9999999999999999999")
        self.assertEqual(status, 400)
        self.assertEqual(response["error"]["code"], "INVALID_ID")

    def test_second_server_cannot_bind_occupied_port(self):
        with self.assertRaises(OSError):
            create_server("127.0.0.1", self.server.server_port, str(self.database_path))


if __name__ == "__main__":
    unittest.main()

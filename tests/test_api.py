"""Smoke tests for the local server. Standard library only, no teacher calls.

Starts the real app (uvicorn) on a spare port with a temporary database and
notes folder, so your data/ and notes/ are never touched.

Run from the project folder:  .venv\\Scripts\\python -m unittest discover tests
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="wp-test-")
        cls.port = free_port()
        cls.notes = Path(cls.tmp.name) / "notes"
        env = dict(os.environ, PORT=str(cls.port), DATA_DIR=str(Path(cls.tmp.name) / "data"),
                   NOTES_DIR=str(cls.notes), RUN_TIMEOUT="2", TEACHER="claude_code")
        cls.server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(cls.port)],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                socket.create_connection(("127.0.0.1", cls.port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.1)
        else:
            cls.server.kill()
            raise RuntimeError("server didn't start")

    @classmethod
    def tearDownClass(cls):
        cls.server.terminate()
        cls.server.wait(10)
        cls.tmp.cleanup()

    def call(self, method, path, body=None, headers=None, host=None):
        h = {"X-Waypoints": "1", "Content-Type": "application/json"}
        h.update(headers or {})
        h["Host"] = host or f"127.0.0.1:{self.port}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw or b"null")
            except ValueError:
                return e.code, raw.decode("utf-8", "replace")

    # ---------- storage ----------
    def test_docs_round_trip(self):
        self.assertEqual(self.call("PUT", "/api/docs/learn/pg1", {"a": 1, "text": "héllo"})[0], 200)
        self.assertEqual(self.call("PUT", "/api/docs/learn/pg1", {"a": 2})[0], 200)  # overwrite
        self.assertEqual(self.call("PUT", "/api/docs/learn/pg3", {"b": True})[0], 200)
        st, body = self.call("GET", "/api/docs/learn")
        self.assertEqual(st, 200)
        self.assertEqual(body["docs"], [{"id": "pg1", "data": {"a": 2}}, {"id": "pg3", "data": {"b": True}}])

    def test_docs_bad_name(self):
        self.assertEqual(self.call("PUT", "/api/docs/learn/bad%20name", {"a": 1})[0], 400)
        self.assertEqual(self.call("GET", "/api/docs/bad%20name")[0], 400)

    # ---------- running Python ----------
    def test_run_prints(self):
        st, body = self.call("POST", "/api/run", {"code": "print(sum(range(5)))"})
        self.assertEqual(st, 200)
        self.assertEqual(body, {"ok": True, "text": "10\n"})

    def test_run_error_is_not_ok(self):
        st, body = self.call("POST", "/api/run", {"code": "1/0"})
        self.assertEqual(st, 200)
        self.assertFalse(body["ok"])
        self.assertIn("ZeroDivisionError", body["text"])

    def test_run_timeout(self):
        st, body = self.call("POST", "/api/run", {"code": "while True: pass"})
        self.assertEqual(st, 200)
        self.assertFalse(body["ok"])
        self.assertTrue(body.get("timeout"))

    def test_run_output_cap(self):
        st, body = self.call("POST", "/api/run", {"code": "print('x' * 100_000)"})
        self.assertEqual(st, 200)
        self.assertLess(len(body["text"]), 21_000)
        self.assertTrue(body["text"].endswith("output cut off"))

    def test_run_code_too_long(self):
        self.assertEqual(self.call("POST", "/api/run", {"code": "#" * 200_001})[0], 413)

    # ---------- security ----------
    def test_foreign_host_refused(self):
        self.assertEqual(self.call("GET", "/api/docs/learn", host="evil.example:8000")[0], 403)
        self.assertEqual(self.call("GET", "/", host=f"attacker.test:{self.port}")[0], 403)

    def test_write_without_header_refused(self):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/run", method="POST",
                                     data=b'{"code": "print(1)"}', headers={"Content-Type": "application/json"})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(cm.exception.code, 403)

    def test_get_needs_no_header(self):
        self.assertEqual(self.call("GET", "/api/limits", headers={"X-Waypoints": ""})[0], 200)

    # ---------- notes ----------
    def test_note_written(self):
        st, _ = self.call("POST", "/api/notes/pg1-learning-log", {"markdown": "# Log\n> [!note] hi\n"})
        self.assertEqual(st, 200)
        self.assertEqual((self.notes / "pg1-learning-log.md").read_text(encoding="utf-8"), "# Log\n> [!note] hi\n")

    def test_note_bad_name_refused(self):
        self.assertEqual(self.call("POST", "/api/notes/bad%20name", {"markdown": "x"})[0], 400)
        # an encoded slash never reaches the handler as one name, so it can't escape the folder
        st, _ = self.call("POST", "/api/notes/..%2F..%2Fescaped", {"markdown": "x"})
        self.assertNotEqual(st, 200)
        self.assertFalse((Path(self.tmp.name).parent / "escaped.md").exists())

    # ---------- the page ----------
    def test_page_served(self):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/", headers={"Host": f"localhost:{self.port}"})
        with urllib.request.urlopen(req, timeout=10) as r:
            self.assertIn(b"WAYPOINTS_LEARN", r.read())


if __name__ == "__main__":
    unittest.main()

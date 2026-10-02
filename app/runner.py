"""Runs Python code for the page: lesson Run buttons, exercise tests, lab code,
and checking quiz answer keys. Real CPython, in a throwaway folder, with a
time limit, so an infinite loop can't freeze anything.

This runs code on your own computer, the same as running a .py file yourself.
The server only listens on 127.0.0.1 and refuses requests from other sites.
"""
import os
import subprocess
import sys
import tempfile

from . import config


def run_python(code: str, timeout: float | None = None) -> dict:
    timeout = timeout or config.RUN_TIMEOUT
    env = {k: v for k, v in os.environ.items() if k.upper() in ("PATH", "SYSTEMROOT", "TEMP", "TMP", "HOME", "USERPROFILE")}
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    with tempfile.TemporaryDirectory(prefix="wp-run-") as workdir:
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-c", code],
                cwd=workdir, env=env, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                timeout=timeout, creationflags=flags,
            )
        except subprocess.TimeoutExpired as e:
            partial = (e.output or b"").decode("utf-8", "replace")
            note = f"\nStopped after {timeout:g} seconds. Is there a loop that never ends?"
            return {"ok": False, "text": (partial + note)[-config.RUN_OUTPUT_CAP:], "timeout": True}
    text = proc.stdout.decode("utf-8", "replace").replace("\r\n", "\n")
    if len(text) > config.RUN_OUTPUT_CAP:
        text = text[: config.RUN_OUTPUT_CAP] + "\n… output cut off"
    return {"ok": proc.returncode == 0, "text": text}

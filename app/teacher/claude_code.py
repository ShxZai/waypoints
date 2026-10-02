"""Teacher route 1: your Claude subscription, through Claude Code's
non-interactive mode (`claude -p`). Each request starts one short Claude Code
session with no file or shell tools, in an empty folder:

    claude -p --no-session-persistence --system-prompt <...> --model <alias>
           --effort <level> --output-format stream-json --include-partial-messages
           --verbose --tools "" [--json-schema <schema>]

Research requests get `--tools WebSearch WebFetch` instead. Output is a stream
of JSON lines: text deltas while writing, rate-limit info, then one "result"
record ("structured_output" holds the validated JSON for --json-schema calls).
Not `--bare`: that mode only accepts an API key, never the subscription login.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import threading

from .. import config
from .base import SYSTEM_PROMPT, AskRequest, Emit, TeacherError, flatten_turns

NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


class ClaudeCodeTeacher:
    name = "claude_code"

    def __init__(self):
        self.exe = shutil.which("claude")
        self.last_limits: dict | None = None
        self._workdir = tempfile.mkdtemp(prefix="wp-teacher-")

    # ---------- status ----------
    def status(self) -> dict:
        if not self.exe:
            return {"ready": False, "message": "Claude Code isn't installed on this computer, so the teacher can't start. Install it, run `claude` once to log in, then restart Waypoints."}
        try:
            out = subprocess.run([self.exe, "auth", "status", "--json"], capture_output=True, timeout=20, creationflags=NO_WINDOW)
            info = json.loads(out.stdout.decode("utf-8", "replace") or "{}")
        except Exception:
            info = {}
        if not info.get("loggedIn"):
            return {"ready": False, "message": "Claude Code isn't logged in. Open a terminal, run `claude`, log in, then reload this page."}
        return {"ready": True, "plan": info.get("subscriptionType"), "limits": self.last_limits}

    # ---------- one request ----------
    def ask(self, req: AskRequest, emit: Emit) -> dict:
        if not self.exe:
            raise TeacherError("not_connected", "Claude Code isn't installed, so the teacher can't start.")
        model, effort = config.CC_MODELS.get(req.tier, config.CC_MODELS["default"])
        args = [
            self.exe, "-p", "--no-session-persistence",
            "--system-prompt", SYSTEM_PROMPT,
            "--model", model, "--effort", effort,
            "--output-format", "stream-json", "--include-partial-messages", "--verbose",
        ]
        if config.CC_FALLBACK_MODEL and config.CC_FALLBACK_MODEL != model:
            args += ["--fallback-model", config.CC_FALLBACK_MODEL]
        if req.web:
            args += ["--tools", "WebSearch", "WebFetch", "--allowedTools", "WebSearch", "WebFetch"]
        else:
            args += ["--tools", ""]
        if req.json and req.schema:
            args += ["--json-schema", json.dumps(req.schema, separators=(",", ":"))]

        prompt = req.input if isinstance(req.input, str) else flatten_turns(req.input)
        proc = subprocess.Popen(
            args, cwd=self._workdir, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, creationflags=NO_WINDOW,
        )
        stderr_chunks: list[bytes] = []
        err_reader = threading.Thread(target=lambda: stderr_chunks.append(proc.stderr.read()), daemon=True)
        err_reader.start()

        finished = threading.Event()

        def watch_cancel():  # the browser stopped the request or went away
            while not finished.wait(0.2):
                if req.cancel.is_set():
                    if proc.poll() is None:
                        proc.kill()
                    return
        threading.Thread(target=watch_cancel, daemon=True).start()

        try:
            proc.stdin.write(prompt.encode("utf-8"))
            proc.stdin.close()
        except OSError:
            pass

        text, final = "", None
        for raw in proc.stdout:
            try:
                ev = json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                continue
            kind = ev.get("type")
            if kind == "stream_event":
                e = ev.get("event") or {}
                if e.get("type") == "content_block_delta":
                    d = e.get("delta") or {}
                    piece = d.get("text") if d.get("type") == "text_delta" else d.get("partial_json") if d.get("type") == "input_json_delta" else None
                    if piece:
                        text += piece
                        emit({"t": "delta", "d": piece})
            elif kind == "rate_limit_event":
                self.last_limits = ev.get("rate_limit_info")
            elif kind == "result":
                final = ev
        proc.wait()
        finished.set()
        err_reader.join(timeout=5)

        if final is None:
            if req.cancel.is_set():
                raise TeacherError("cancelled", "Stopped.", text or None)
            err = b"".join(stderr_chunks).decode("utf-8", "replace").strip()
            low = err.lower()
            if "log in" in low or "login" in low or "auth" in low:
                raise TeacherError("not_connected", "Claude Code isn't logged in. Run `claude` in a terminal to log in.", text or None)
            raise TeacherError("upstream_error", err[-500:] or "Claude Code stopped without an answer.", text or None)

        if final.get("is_error") or final.get("subtype") != "success":
            status = final.get("api_error_status")
            msg = str(final.get("result") or "Claude Code reported an error.")
            if status == 429 or "limit" in msg.lower():
                raise TeacherError("rate_limited", "You've reached your Claude usage limit for now. It resets later; see the usage line in the rail.", text or None)
            raise TeacherError("upstream_error", msg[:500], text or None)

        result_text = final.get("result") or ""
        if req.json:
            value = final.get("structured_output")
            if value is None:
                value = parse_json_loosely(result_text)
            if value is None:
                raise TeacherError("invalid_json", "The reply came back in the wrong shape.", result_text)
        else:
            value = result_text
        usage = {
            "cost_usd_equivalent": final.get("total_cost_usd"),
            "duration_ms": final.get("duration_ms"),
            "models": list((final.get("modelUsage") or {}).keys()),
        }
        return {"result": value, "text": result_text if not req.json else json.dumps(value), "usage": usage}


def parse_json_loosely(s: str):
    """Whole text as JSON; else a ```json fence; else first { or [ to last } or ]."""
    s = (s or "").strip()
    for candidate in (s, _fence(s), _span(s)):
        if candidate:
            try:
                return json.loads(candidate)
            except ValueError:
                pass
    return None


def _fence(s: str) -> str | None:
    if "```" not in s:
        return None
    body = s.split("```", 2)
    if len(body) < 3:
        return None
    inner = body[1]
    return inner[4:].strip() if inner.lower().startswith("json") else inner.strip()


def _span(s: str) -> str | None:
    starts = [i for i in (s.find("{"), s.find("[")) if i >= 0]
    ends = [i for i in (s.rfind("}"), s.rfind("]")) if i >= 0]
    if not starts or not ends:
        return None
    a, b = min(starts), max(ends)
    return s[a : b + 1] if b > a else None

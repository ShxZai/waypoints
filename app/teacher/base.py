"""Shared shape for both teacher routes.

Error codes match what the page already handles (see tutorError in
web/index.html): rate_limited, invalid_json, not_connected, cancelled,
upstream_error, ...
"""
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

# Stable, short instructions for every call. The real teaching instructions
# (philosophy, style, quiz rules) travel in each request's prompt.
SYSTEM_PROMPT = (
    "You are the learner's one personal programming teacher inside their Waypoints study app. "
    "Each message contains your full instructions and the learner's context. Follow them exactly, "
    "and answer in the format they ask for."
)

Emit = Callable[[dict], None]


@dataclass
class AskRequest:
    input: Any                      # a prompt string, or [{role, content}, ...] ending on a user turn
    json: bool = False              # expect a JSON value back
    schema: dict | None = None      # JSON Schema the reply must match (JSON tasks)
    tier: str = "default"           # quick | default | complex
    web: bool = False               # allow web search + fetch (research tasks)
    cancel: threading.Event = field(default_factory=threading.Event)


class TeacherError(Exception):
    def __init__(self, code: str, message: str, text: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.text = text


class Teacher(Protocol):
    name: str

    def status(self) -> dict: ...

    def ask(self, req: AskRequest, emit: Emit) -> dict:
        """Run one request. Calls emit({"t": "delta", "d": text}) while writing.
        Returns {"result": value, "text": str, "usage": {...}} or raises TeacherError."""
        ...


def flatten_turns(turns: list[dict]) -> str:
    """A chat (list of turns) as one prompt, for routes that take a single message.
    The first user turn holds the standing instructions."""
    if not turns:
        return ""
    head, rest = turns[0]["content"], turns[1:]
    if not rest:
        return head
    lines = [head, "", "The conversation so far (oldest first):"]
    for t in rest[:-1]:
        who = "Learner" if t["role"] == "user" else "You (teacher)"
        lines += ["", f"{who}: {t['content']}"]
    lines += ["", "The learner's new message, which you are answering now:", rest[-1]["content"]]
    return "\n".join(lines)

"""Teacher route 2: an Anthropic API key (pay per use). Turn it on with
TEACHER=api and ANTHROPIC_API_KEY=... in .env.

Streams the reply, uses structured outputs for JSON tasks, caches the stable
system prompt, and gives research requests the server-side web search and
web fetch tools (resuming if the server pauses a long research turn).
"""
import json
import os

from .. import config
from .base import SYSTEM_PROMPT, AskRequest, Emit, TeacherError
from .claude_code import parse_json_loosely

# $ per million tokens (input, output), for the per-session cost display.
PRICES = {"claude-opus-5": (5.0, 25.0), "claude-sonnet-5": (2.0, 10.0), "claude-haiku-4-5": (1.0, 5.0)}
WEB_TOOLS = [
    {"type": "web_search_20260209", "name": "web_search", "max_uses": 8},
    {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 6},
]
MAX_CONTINUATIONS = 4


def strict_schema(schema):
    """Structured outputs want every object to forbid extra keys."""
    if isinstance(schema, dict):
        out = {k: strict_schema(v) for k, v in schema.items()}
        if out.get("type") == "object" and "additionalProperties" not in out:
            out["additionalProperties"] = False
        return out
    if isinstance(schema, list):
        return [strict_schema(v) for v in schema]
    return schema


class ApiTeacher:
    name = "api"

    def __init__(self):
        import anthropic  # only needed on this route
        self._anthropic = anthropic
        self.client = anthropic.Anthropic() if os.getenv("ANTHROPIC_API_KEY") else None
        self.last_limits = None

    def status(self) -> dict:
        if not self.client:
            return {"ready": False, "message": "TEACHER=api is set but there's no ANTHROPIC_API_KEY in .env. Add your key, then restart Waypoints."}
        return {"ready": True, "plan": "api"}

    def ask(self, req: AskRequest, emit: Emit) -> dict:
        if not self.client:
            raise TeacherError("not_connected", "No ANTHROPIC_API_KEY is set in .env.")
        a = self._anthropic
        model, effort = config.API_MODELS.get(req.tier, config.API_MODELS["default"])
        messages = [{"role": "user", "content": req.input}] if isinstance(req.input, str) else [
            {"role": t["role"], "content": t["content"]} for t in req.input]
        output_config = {"effort": effort}
        if req.json and req.schema:
            output_config["format"] = {"type": "json_schema", "schema": strict_schema(req.schema)}
        kwargs = dict(
            model=model, max_tokens=32000, system=SYSTEM_PROMPT, messages=messages,
            thinking={"type": "adaptive"}, output_config=output_config,
            cache_control={"type": "ephemeral"},
        )
        if req.web:
            kwargs["tools"] = WEB_TOOLS

        usage = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
        try:
            try:
                msg = self._run(kwargs, req, emit, usage)
            except a.BadRequestError:
                if "format" not in output_config:
                    raise
                output_config.pop("format")  # schema not accepted: fall back to instructions + parsing
                msg = self._run(kwargs, req, emit, usage)
        except a.RateLimitError:
            raise TeacherError("rate_limited", "The API rate limit was hit. Wait a minute and try again.")
        except a.AuthenticationError:
            raise TeacherError("not_connected", "The API key in .env was rejected. Check it in the Anthropic console.")
        except a.APIConnectionError:
            raise TeacherError("upstream_error", "Couldn't reach the Anthropic API. Check your internet connection.")
        except a.APIStatusError as e:
            raise TeacherError("upstream_error", f"API error {e.status_code}: {e.message}")

        if msg.stop_reason == "refusal":
            raise TeacherError("refused", "The model declined this request.")
        text = "".join(b.text for b in msg.content if b.type == "text")
        if req.json:
            value = parse_json_loosely(text)
            if value is None:
                raise TeacherError("invalid_json", "The reply came back in the wrong shape.", text)
        else:
            value = text
            if msg.stop_reason == "max_tokens":
                value += "\n\n*(This answer was cut short.)*"
        price_in, price_out = PRICES.get(model, (0.0, 0.0))
        cost = (usage["input"] * price_in + usage["cache_write"] * price_in * 1.25
                + usage["cache_read"] * price_in * 0.1 + usage["output"] * price_out) / 1_000_000
        return {"result": value, "text": text, "usage": {"cost_usd": round(cost, 5), "models": [model], **usage}}

    def _run(self, kwargs, req: AskRequest, emit: Emit, usage: dict):
        messages = list(kwargs["messages"])
        for _ in range(MAX_CONTINUATIONS + 1):
            with self.client.messages.stream(**{**kwargs, "messages": messages}) as stream:
                for event in stream:
                    if req.cancel.is_set():
                        stream.close()
                        raise TeacherError("cancelled", "Stopped.")
                    if event.type == "content_block_delta" and event.delta.type == "text_delta":
                        emit({"t": "delta", "d": event.delta.text})
                msg = stream.get_final_message()
            u = msg.usage
            usage["input"] += u.input_tokens or 0
            usage["output"] += u.output_tokens or 0
            usage["cache_read"] += getattr(u, "cache_read_input_tokens", 0) or 0
            usage["cache_write"] += getattr(u, "cache_creation_input_tokens", 0) or 0
            if msg.stop_reason != "pause_turn":
                return msg
            # A long research turn paused server-side: send it back to resume.
            messages = messages + [{"role": "assistant", "content": msg.content}]
        return msg

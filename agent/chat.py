"""Web chat agent: one model call picks a tool; the backend's ready text is the reply.

The model understands the technician and chooses tool and arguments (including the autonomous
record_answer call). It never restates data: tool results are rendered deterministically and
returned as they are, so no value can change on the way and a turn costs one model call.
"""

import asyncio
import inspect
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from student_b.cases import utc_now
from student_b.source import Failure

from .tools import TOOL_SPECS, Session, Toolbox

INSTRUCTIONS = (Path(__file__).parent / "instructions.md").read_text(encoding="utf-8")
SHOWN = "[The tool result was shown to the technician in full.]"
FORBIDDEN_MODELS = {"auto", "fusion", "default"}


@dataclass(frozen=True)
class AgentConfig:
    models: tuple[str, ...] = ()
    expected_routes: frozenset[str] = frozenset()
    reasoning_effort: str | None = "low"
    allow_real_data: bool = False
    rate_limit_waits: tuple[int, ...] = (4, 8, 12)
    max_history: int = 24
    max_conversations: int = 50
    conversation_ttl_seconds: int = 7200
    model_timeout_seconds: int = 30

    @property
    def enabled(self) -> bool:
        return bool(self.models) and bool(os.environ.get("OPENAI_API_KEY"))

    @classmethod
    def from_environment(cls) -> "AgentConfig":
        models = tuple(m.strip() for m in os.environ.get("OPENAI_MODEL", "").split(",") if m.strip())
        for model in models:
            if model.lower() in FORBIDDEN_MODELS or model.lower().startswith("auto:"):
                raise ValueError(f"OPENAI_MODEL '{model}' switches models per request; list fixed model IDs")
        effort = os.environ.get("TRACE_REASONING_EFFORT", "low").strip().lower()
        return cls(
            models=models,
            expected_routes=frozenset(r.strip() for r in os.environ.get("TRACE_EXPECTED_ROUTE", "").split(",") if r.strip()),
            reasoning_effort=None if effort in ("", "off", "none") else effort,
            allow_real_data=os.environ.get("TRACE_ALLOW_REAL_DATA") == "1",
        )


@dataclass
class Conversation:
    conversation_id: str
    session: Session = field(default_factory=Session)
    messages: list = field(default_factory=list)
    last_used: float = field(default_factory=time.monotonic)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class ModelUnavailable(Exception):
    pass


class ChatAgent:
    def __init__(self, toolbox: Toolbox, config: AgentConfig, client=None) -> None:
        self.toolbox, self.config = toolbox, config
        self._client = client
        self._conversations: dict[str, Conversation] = {}
        # Outcome of the latest model call, for the dashboard status chip (no extra model calls).
        self.last_model_ok: str | None = None
        self.last_model_error: str | None = None

    def _model_client(self):
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(max_retries=0)  # OPENAI_API_KEY / OPENAI_BASE_URL from the environment
        return self._client

    def conversation(self, conversation_id: str | None) -> Conversation:
        now = time.monotonic()
        for key, conv in tuple(self._conversations.items()):
            if not conv.lock.locked() and now - conv.last_used > self.config.conversation_ttl_seconds:
                del self._conversations[key]
        conv = self._conversations.get(conversation_id or "")
        if conv is None:
            if len(self._conversations) >= self.config.max_conversations:
                idle = [c for c in self._conversations.values() if not c.lock.locked()]
                if not idle:
                    raise Failure("SOURCE_UNAVAILABLE", "Conversation capacity is busy; retry later", 503)
                oldest = min(idle, key=lambda c: c.last_used)
                del self._conversations[oldest.conversation_id]
            conv = Conversation(uuid.uuid4().hex)
            self._conversations[conv.conversation_id] = conv
        conv.last_used = now
        return conv

    def _window(self, messages: list) -> list:
        """System prompt plus the recent history, starting at a technician message."""
        recent = messages[-self.config.max_history:]
        while recent and recent[0]["role"] != "user":
            recent = recent[1:]
        return [{"role": "system", "content": INSTRUCTIONS}, *recent]

    async def _complete(self, messages: list):
        """Try the configured models in order; wait only when all are rate-limited."""
        from openai import APIError, RateLimitError
        client, last = self._model_client(), None
        for attempt in range(len(self.config.rate_limit_waits) + 1):
            for model in self.config.models:
                extra = ({"reasoning_effort": self.config.reasoning_effort}
                         if self.config.reasoning_effort and "gpt-oss" in model else None)
                try:
                    raw = await client.chat.completions.with_raw_response.create(
                        model=model, messages=messages, tools=TOOL_SPECS, extra_body=extra)
                except RateLimitError as exc:
                    last = exc
                    continue
                except APIError as exc:
                    raise ModelUnavailable(type(exc).__name__) from None
                served = unquote(raw.headers.get("x-routed-via") or "") or model
                routes = self.config.expected_routes
                if routes and (not raw.headers.get("x-routed-via") or served not in routes):
                    last = ModelUnavailable(f"unapproved route {served}")
                    continue  # never accept an answer from a model/provider that was not approved
                parsed = raw.parse()
                if inspect.isawaitable(parsed):
                    parsed = await parsed
                # Validate the whole plan before any tool can change case state.
                if not getattr(parsed, "choices", None) or len(parsed.choices) != 1:
                    raise ModelUnavailable("invalid provider response")
                message = getattr(parsed.choices[0], "message", None)
                if message is None or not hasattr(message, "tool_calls"):
                    raise ModelUnavailable("invalid provider response")
                calls = message.tool_calls or []
                if len(calls) > 1:
                    raise ModelUnavailable("only one tool action is allowed per turn")
                for call in calls:
                    function = getattr(call, "function", None)
                    if (not isinstance(getattr(call, "id", None), str)
                            or not isinstance(getattr(function, "name", None), str)
                            or not isinstance(getattr(function, "arguments", None), str)
                            or len(function.arguments) > 8192):
                        raise ModelUnavailable("invalid provider tool call")
                return parsed, served
            if attempt < len(self.config.rate_limit_waits):
                await asyncio.sleep(self.config.rate_limit_waits[attempt])
        raise ModelUnavailable(type(last).__name__ if last else "no model configured")

    async def turn(self, conv: Conversation, text: str) -> dict:
        start = len(conv.messages)
        conv.messages.append({"role": "user", "content": text})
        try:
            response, served = await asyncio.wait_for(
                self._complete(self._window(conv.messages)), self.config.model_timeout_seconds)
            self.last_model_ok, self.last_model_error = utc_now().isoformat(), None
        except (ModelUnavailable, TimeoutError, ValueError, AttributeError, TypeError) as exc:
            self.last_model_error = utc_now().isoformat()
            del conv.messages[start:]
            return {"reply": "The language model is not available right now (rate limit or provider problem). "
                             "Nothing was changed; please send your message again in a moment.",
                    "tool_calls": [], "model": None, "model_error": type(exc).__name__}
        message = response.choices[0].message
        if not message.tool_calls:
            # Prose from an untrusted model is not a source of manufacturing facts
            # or approved procedures. Only deterministic tool output is displayed.
            reply = ("I can investigate a station, show captured evidence, record your answer or provide a handover. "
                     "I can't advise on physical interventions or establish a cause without approved evidence. "
                     "Which data check would you like?")
            conv.messages.append({"role": "assistant", "content": reply})
            return {"reply": reply, "tool_calls": [], "model": served}

        conv.messages.append({"role": "assistant", "content": None, "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}}
            for c in message.tool_calls]})
        texts, calls = [], []
        for call in message.tool_calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
                if not isinstance(args, dict):
                    raise ValueError
            except ValueError:
                shown, compact = "The tool call had unreadable arguments.", {"status": "error", "code": "BAD_ARGUMENTS"}
            else:
                if not self.config.allow_real_data:
                    shown, compact = ("Live investigation is disabled: sending manufacturing data to the model "
                                      "provider has not been approved (TRACE_ALLOW_REAL_DATA).",
                                      {"status": "error", "code": "DATA_SHARING_NOT_APPROVED"})
                else:
                    if name == "record_answer":
                        # The model selects the action, never the technician's testimony.
                        args["answer_text"] = text
                    shown, compact = await self.toolbox.run(conv.session, name, args)
            texts.append(shown)
            calls.append({"name": name, "status": compact.get("status"), "code": compact.get("code"),
                          "request_id": compact.get("request_id")})
            conv.messages.append({"role": "tool", "tool_call_id": call.id,
                                  "content": json.dumps(compact, ensure_ascii=False, separators=(",", ":"))})
        conv.messages.append({"role": "assistant", "content": SHOWN})
        return {"reply": "\n\n".join(texts), "tool_calls": calls, "model": served}

    async def aclose(self) -> None:
        if self._client is not None and hasattr(self._client, "close"):
            result = self._client.close()
            if inspect.isawaitable(result):
                await result


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = Field(None, max_length=64)


def make_chat_router(agent: ChatAgent, authenticate) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.post("/chat", operation_id="chat")
    async def chat(body: ChatRequest, request: Request):
        authenticate(request)
        if not agent.config.enabled:
            raise Failure("SOURCE_UNAVAILABLE", "The agent model is not configured on the server "
                                                "(OPENAI_API_KEY, OPENAI_MODEL).", 503)
        text = body.message.strip()
        if not text:
            raise Failure("INVALID_SCOPE", "Message is empty", 422)
        conv = agent.conversation(body.conversation_id)
        async with conv.lock:
            try:
                result = await agent.turn(conv, text)
            finally:
                # Bound stored history, not merely the subset sent to the provider.
                conv.messages[:] = agent._window(conv.messages)[1:]
                conv.last_used = time.monotonic()
        return {
            "request_id": request.scope["b_request_id"], "retrieved_at": utc_now().isoformat(),
            "status": "ok", "case_id": conv.session.case_id, "error": None,
            "data": {"conversation_id": conv.conversation_id, **result,
                     "open_question": conv.session.question_id is not None},
        }

    @router.get("/status", operation_id="status")
    def status(request: Request):
        """Readiness for the dashboard chip: Oracle via the read-only count, model from the last call."""
        authenticate(request)
        try:
            count = request.app.state.source.count_measurements()
            oracle = "ok" if type(count) is int and count >= 0 else "error"
        except Exception:
            oracle = "error"
        model = ("not_configured" if not agent.config.enabled else
                 "error" if agent.last_model_error and (agent.last_model_ok or "") < agent.last_model_error else
                 "ok" if agent.last_model_ok else "unused")
        return {
            "request_id": request.scope["b_request_id"], "retrieved_at": utc_now().isoformat(),
            "status": "ok", "case_id": None, "error": None,
            "data": {"oracle": oracle, "model": model, "last_model_ok": agent.last_model_ok,
                     "last_model_error": agent.last_model_error},
        }

    return router

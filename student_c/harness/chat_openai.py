"""MAGNA TRACE - interim chat harness: OpenAI model + our MCP server.

Stand-in for the Copilot Studio agent while the Copilot environment has no credits.
It uses the SAME MCP server (/mcp) and the SAME instructions (copilot/instructions.md)
that Copilot Studio will use. Switching to Copilot means configuring Copilot Studio;
nothing in the backend changes and this file is simply no longer used.

This is an engineering harness. It is not the product interface and not G0 evidence.

Configuration (environment variables only; never commit them):
  TRACE_MCP_URL          e.g. http://127.0.0.1:8000/mcp  (local; no tunnel needed)
  TRACE_API_KEY          the backend API key
  TRACE_API_KEY_HEADER   header name, default X-API-Key
  OPENAI_API_KEY         API key of the model provider
  OPENAI_MODEL           model name with tool calling support
  OPENAI_BASE_URL        optional: any OpenAI-compatible endpoint (read by the OpenAI client
                         itself), e.g. a local FreeLLMAPI router http://localhost:3001/v1
  TRACE_ALLOW_REAL_DATA  set to 1 ONLY after the organizers approve sending MAGNA data to
                         the chosen provider; until then only health_echo results reach the model
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from urllib.parse import unquote

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from openai import APIError, OpenAI, RateLimitError

ROOT = Path(__file__).resolve().parent.parent
INSTRUCTIONS_FILE = ROOT / "copilot" / "instructions.md"
MAX_TOOL_ROUNDS = 6  # tool-call rounds allowed per technician message

# Router models that switch the underlying model per request. Agent behaviour must be
# reproducible (e.g. whether record_answer is called), so one fixed model is required.
FORBIDDEN_MODELS = {"auto", "fusion"}
# The router may still fail over to another model when the pinned one is rate-limited.
# By default such answers are discarded; set TRACE_ALLOW_MODEL_FALLBACK=1 to only warn.
MODEL_FALLBACK_ALLOWED = os.environ.get("TRACE_ALLOW_MODEL_FALLBACK") == "1"
# Exact provider/model route expected in X-Routed-Via, e.g. groq/openai/gpt-oss-120b.
EXPECTED_ROUTE = os.environ.get("TRACE_EXPECTED_ROUTE") or None

# Data guard: until the organizers approve sending MAGNA data to this model provider,
# only tools that return no manufacturing data are forwarded to the model.
TOOLS_WITHOUT_MAGNA_DATA = {"health_echo"}
REAL_DATA_ALLOWED = os.environ.get("TRACE_ALLOW_REAL_DATA") == "1"


def env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if not value:
        sys.exit(f"Missing environment variable: {name}")
    return value


def served_model(headers) -> str | None:
    """FreeLLMAPI reports the model that really answered as 'X-Routed-Via: <platform>/<model>'."""
    value = headers.get("x-routed-via")
    return unquote(value) if value else None


def is_pinned_model(requested: str, served: str, expected_route: str | None = None) -> bool:
    """True if the answer came from the pinned model.

    TRACE_EXPECTED_ROUTE is one route or a comma-separated list of approved routes, e.g.
    'groq/openai/gpt-oss-120b,cerebras/gpt-oss-120b'. The served route must match one of them
    exactly, which pins both the model and the provider (and therefore its data policy).
    Without it, the served route must end with the requested id.
    """
    if expected_route:
        return served in {r.strip() for r in expected_route.split(",") if r.strip()}
    return served == requested or served.endswith("/" + requested)


def check_model(model: str) -> str:
    if model.lower() in FORBIDDEN_MODELS or model.lower().startswith("auto:"):
        sys.exit(
            f"OPENAI_MODEL='{model}' switches models per request. Set one fixed model ID "
            "with tool calling support (see docs/llm_router_setup.md)."
        )
    return model


def to_openai_tool(tool) -> dict:
    """MCP tool definition -> OpenAI function-tool definition (same name, description, schema)."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema or {"type": "object", "properties": {}},
        },
    }


def result_to_text(result) -> str:
    """Pass the backend envelope to the model unchanged; mark protocol-level failures."""
    structured = getattr(result, "structuredContent", None)
    if structured:
        # Compact separators: same content, fewer tokens (free tiers limit tokens per minute).
        text = json.dumps(structured, ensure_ascii=False, separators=(",", ":"))
    else:
        text = "\n".join(c.text for c in result.content if getattr(c, "type", "") == "text")
    if getattr(result, "isError", False):
        return f"TOOL ERROR: {text}"
    return text


def short(text: str) -> str:
    """One-line trace for the console: status and request_id if the envelope is JSON."""
    try:
        data = json.loads(text)
        error = (data.get("error") or {}).get("code")
        return f"status={data.get('status')} request_id={data.get('request_id')}" + (
            f" error={error}" if error else ""
        )
    except (ValueError, AttributeError):
        return text[:120].replace("\n", " ")


async def call_tool(session: ClientSession, name: str, raw_args: str) -> str:
    try:
        args = json.loads(raw_args or "{}")
    except ValueError:
        return "TOOL ERROR: the model sent arguments that are not valid JSON; the tool was not called."
    print(f"  [tool] {name}({json.dumps(args, ensure_ascii=False)})")
    if not REAL_DATA_ALLOWED and name not in TOOLS_WITHOUT_MAGNA_DATA:
        print("  [guard] blocked: real MAGNA data is not approved for this model provider")
        return (
            "TOOL BLOCKED: this tool returns manufacturing data, and sending it to the current "
            "model provider is not approved yet. No data was retrieved. Tell the user that live "
            "investigation is disabled in this test setup until data sharing is approved."
        )
    try:
        text = result_to_text(await session.call_tool(name, args))
    except Exception as exc:  # backend down, tunnel down, auth failure
        text = f"TOOL ERROR: the MAGNA TRACE backend could not be reached ({type(exc).__name__}). No data was returned."
    print(f"  [tool] -> {short(text)}")
    return text


# Free tiers limit tokens per minute. After a tool result the next model call is large, so a
# 429 usually clears within a minute: wait and retry instead of dropping the technician's turn.
RATE_LIMIT_WAITS = (20, 30, 40)


KEEP_FULL_TOOL_RESULTS = 1  # older tool results are shortened in what the model receives
KEEP_FULL_REPLIES = 2       # older agent replies to the technician are shortened too

# gpt-oss models spend hidden reasoning tokens, which count against the per-minute limit.
# 'low' cut completion tokens ~3.7x in a probe (491 -> 133). Set TRACE_REASONING_EFFORT to
# 'medium'/'high' if rule-following suffers, or to 'off' to send no reasoning parameter.
_effort = os.environ.get("TRACE_REASONING_EFFORT", "low").strip().lower()
REASONING_EFFORT = None if _effort in ("", "off", "none") else _effort


def reasoning_params(model: str) -> dict | None:
    """Only gpt-oss models take low/medium/high; Qwen on Groq uses other values and needs none here."""
    return {"reasoning_effort": REASONING_EFFORT} if REASONING_EFFORT and "gpt-oss" in model else None


def compact_history(messages: list[dict], keep: int = KEEP_FULL_TOOL_RESULTS) -> list[dict]:
    """Copy of the history where all but the last `keep` tool results are replaced by a stub.

    The stored history is not changed. Assistant messages (with case_id / question_id in their
    text and tool-call arguments) stay intact, so the model keeps the case context; the latest
    snapshot is always among the full results.
    """
    tool_positions = [i for i, msg in enumerate(messages) if msg.get("role") == "tool"]
    shorten = set(tool_positions[:-keep]) if keep else set(tool_positions)
    # Older long agent replies (tables) are also stubbed; their tool calls, which carry case_id
    # and question_id, are kept, and the last KEEP_FULL_REPLIES replies stay in full.
    reply_positions = [i for i, msg in enumerate(messages)
                       if msg.get("role") == "assistant" and msg.get("content")]
    old_replies = set(reply_positions[:-KEEP_FULL_REPLIES]) if KEEP_FULL_REPLIES else set(reply_positions)
    out = []
    for i, msg in enumerate(messages):
        if i in shorten:
            out.append({**msg, "content": f"[earlier tool result omitted to save tokens; {short(msg['content'])}. "
                                          "Call the tool again if you need these details.]"})
        elif i in old_replies:
            out.append({**msg, "content": "[earlier reply to the technician omitted to save tokens]"})
        else:
            out.append(msg)
    return out


async def create_with_rate_limit_wait(client: OpenAI, models: list[str], messages: list[dict], tools: list[dict]):
    """Return (raw response, model used), or (None, None) after printing a non-recoverable error.

    Models are tried in the configured order. Each Groq model has its own per-minute limit, so on
    a 429 the next model is tried at once; only when all are limited does the client wait.
    """
    payload = compact_history(messages)
    last_exc = None
    for attempt in range(len(RATE_LIMIT_WAITS) + 1):
        for model in models:
            try:
                raw = client.chat.completions.with_raw_response.create(
                    model=model, messages=payload, tools=tools or None,
                    extra_body=reasoning_params(model),
                )
                return raw, model
            except RateLimitError as exc:
                last_exc = exc
                if len(models) > 1:
                    print(f"  [rate limit] {model} is at its limit or on router cooldown; trying the next model")
            except APIError as exc:
                # Model provider problem (credits, model name, auth). Keep the session alive.
                print(f"\n[model error] {model}: {type(exc).__name__}: {getattr(exc, 'message', exc)}")
                return None, None
        if attempt == len(RATE_LIMIT_WAITS):
            break
        wait = RATE_LIMIT_WAITS[attempt]
        print(f"  [rate limit] all models limited or on cooldown; waiting {wait} s and retrying "
              f"({attempt + 1}/{len(RATE_LIMIT_WAITS)})")
        await asyncio.sleep(wait)
    print(f"\n[model error] still rate-limited after {sum(RATE_LIMIT_WAITS)} s: "
          f"{getattr(last_exc, 'message', last_exc)}")
    return None, None


# Tool results that carry a ready-made `message` (or handover `text`) are shown as they are,
# instead of asking the model to restate them. The instructions already require relaying these
# texts unchanged, so the second model call only cost tokens and invited wording drift.
RELAY_TOOL_TEXT = os.environ.get("TRACE_RELAY_TOOL_TEXT", "1") != "0"


def relay_ready_text(messages: list[dict]) -> str | None:
    """If the last tool result is ok and has a ready text, record it as the agent's reply.

    The stored tool result keeps all structured data (IDs for later turns) but drops the text,
    which now lives in the appended assistant message, so nothing is sent to the model twice.
    """
    if not RELAY_TOOL_TEXT:
        return None
    try:
        envelope = json.loads(messages[-1]["content"])
    except (ValueError, TypeError):
        return None
    data = envelope.get("data") if isinstance(envelope, dict) else None
    if envelope.get("status") != "ok" or not isinstance(data, dict):
        return None  # errors go back to the model so it can explain them
    text = data.get("message") or data.get("text")
    if not text:
        return None
    slim = {k: v for k, v in data.items() if k not in ("message", "text")}
    messages[-1] = {**messages[-1], "content": json.dumps({**envelope, "data": slim},
                                                          ensure_ascii=False, separators=(",", ":"))}
    messages.append({"role": "assistant", "content": text})
    return text


async def main() -> None:
    url = env("TRACE_MCP_URL")
    headers = {env("TRACE_API_KEY_HEADER", "X-API-Key"): env("TRACE_API_KEY")}
    # OPENAI_MODEL: one model id, or a comma-separated list in order of preference.
    models = [check_model(m.strip()) for m in env("OPENAI_MODEL").split(",") if m.strip()]
    env("OPENAI_API_KEY")  # read by the OpenAI client itself
    client = OpenAI(max_retries=0)  # rate-limit retries are handled with longer waits below
    messages: list[dict] = [{"role": "system", "content": INSTRUCTIONS_FILE.read_text(encoding="utf-8")}]

    # Windows' Proactor loop logs "ConnectionResetError [WinError 10054]" when an idle HTTP
    # connection is closed during a long rate-limit wait. The next call reconnects; hide only that.
    loop = asyncio.get_running_loop()
    previous = loop.get_exception_handler()

    def quiet_connection_reset(loop, context):
        if isinstance(context.get("exception"), ConnectionResetError):
            return
        (previous or (lambda lp, ctx: lp.default_exception_handler(ctx)))(loop, context)

    loop.set_exception_handler(quiet_connection_reset)

    async with streamablehttp_client(url, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            openai_tools = [to_openai_tool(t) for t in tools]
            print("MAGNA TRACE - interim chat client (stand-in for Microsoft Copilot: no Copilot credits).")
            print("Tools:", ", ".join(t.name for t in tools) or "none")
            print(f"Models (in order): {', '.join(models)} via {os.environ.get('OPENAI_BASE_URL', 'api.openai.com')}")
            print("Pinned routes:", EXPECTED_ROUTE or "any provider, model id ending in the requested model")
            print("Reasoning effort:", f"{REASONING_EFFORT} (gpt-oss models only)" if REASONING_EFFORT else "provider default")
            print("Real MAGNA data to model:", "ALLOWED" if REAL_DATA_ALLOWED else "BLOCKED (only health_echo)")
            print("Backend texts:", "shown as is (one model call per turn)" if RELAY_TOOL_TEXT else "restated by the model")
            print("Type /quit to exit.")

            while True:
                try:
                    user = (await asyncio.to_thread(input, "\ntechnician> ")).strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if user in {"/quit", "/exit"}:
                    break
                if not user:
                    continue
                turn_start = len(messages)
                messages.append({"role": "user", "content": user})

                for _ in range(MAX_TOOL_ROUNDS):
                    raw, model = await create_with_rate_limit_wait(client, models, messages, openai_tools)
                    if raw is None:
                        del messages[turn_start:]  # drop the whole unanswered turn
                        break
                    served = served_model(raw.headers)
                    response = raw.parse()
                    usage = getattr(response, "usage", None)
                    tokens = f" (in {usage.prompt_tokens}, out {usage.completion_tokens} tokens)" if usage else ""
                    print(f"  [model] {served or model}{tokens}")
                    if served and not is_pinned_model(model, served, EXPECTED_ROUTE):
                        if not MODEL_FALLBACK_ALLOWED:
                            print(f"\n[guard] answer came from {served}, not the pinned {EXPECTED_ROUTE or model}; discarded.")
                            print("        The pinned model is probably rate-limited. Wait, or pin another model.")
                            del messages[turn_start:]
                            break
                        print(f"  [warn] answered by {served}, not the pinned model {model}")
                    reply = response.choices[0].message
                    messages.append(reply.model_dump(exclude_none=True))
                    if not reply.tool_calls:
                        print(f"\ntrace> {reply.content}")
                        break
                    for call in reply.tool_calls:
                        output = await call_tool(session, call.function.name, call.function.arguments)
                        messages.append({"role": "tool", "tool_call_id": call.id, "content": output})
                    relayed = relay_ready_text(messages) if len(reply.tool_calls) == 1 else None
                    if relayed:
                        print("  [relay] backend text shown as is; no second model call")
                        print(f"\ntrace> {relayed}")
                        break
                else:
                    print("\ntrace> Stopped: too many tool calls for one message. Please rephrase.")


if __name__ == "__main__":
    asyncio.run(main())

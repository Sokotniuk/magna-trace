"""MAGNA TRACE — the integrated application.

    python -m uvicorn agent.main:create_app --factory --host 127.0.0.1 --port 8000 --workers 1

Student B's FastAPI (contract B2, cases, evidence) with student A's Oracle modules, plus the
agent layer of student C: POST /api/v1/chat for the web dashboard and /mcp for MCP clients.
"""

import os
import secrets
from contextlib import asynccontextmanager
from dataclasses import replace

from fastapi import FastAPI, Request

from student_b.main import Settings, create_app as create_backend
from student_b.source import DataSource, Failure

from .chat import AgentConfig, ChatAgent, make_chat_router
from .mcp_server import KeyGuard, build_mcp
from .tools import Toolbox


def create_app(settings: Settings | None = None, source: DataSource | None = None,
               agent_config: AgentConfig | None = None, model_client=None) -> FastAPI:
    if settings is None:
        # One chat turn makes several in-process API calls, so the shared limit is raised.
        settings = replace(Settings.from_environment(),
                           requests_per_minute=int(os.environ.get("TRACE_REQUESTS_PER_MINUTE", "300")))
    app = create_backend(settings, source)

    def key_ok(key: str) -> bool:
        return secrets.compare_digest(key.encode(), settings.api_key.encode())

    def authenticate(request: Request) -> None:
        keys = request.headers.getlist("x-api-key")
        if len(keys) != 1 or not key_ok(keys[0]):
            raise Failure("UNAUTHORIZED", "Valid connector credentials are required", 401)

    toolbox = Toolbox(app, settings.api_key)
    agent = ChatAgent(toolbox, agent_config or AgentConfig.from_environment(), model_client)
    app.state.agent = agent
    app.include_router(make_chat_router(agent, authenticate))

    mcp = build_mcp(toolbox)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        async with mcp.session_manager.run():
            yield
        await toolbox.aclose()

    app.router.lifespan_context = lifespan
    # Serves /mcp. Mounted last so it only receives paths no REST route matched.
    app.mount("/", KeyGuard(mcp.streamable_http_app(), key_ok))
    return app

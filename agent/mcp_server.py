"""MCP endpoint (/mcp) for Microsoft Copilot Studio or any MCP client.

Same tools as the web chat, but stateless: the client passes case_id and question_id itself.
Each result carries the ready-made `message` for the technician plus the compact data.
"""

from mcp.server.fastmcp import FastMCP

from student_b.main import error_response
from student_b.source import Failure

from .tools import Session, Toolbox

RELAY = " The result contains `message`: show it to the technician as it is, without changing any value or ID."


def build_mcp(toolbox: Toolbox) -> FastMCP:
    kwargs = {}
    try:  # API-key auth protects the endpoint; Host checks would reject tunnel host names.
        from mcp.server.transport_security import TransportSecuritySettings
        kwargs["transport_security"] = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    except ImportError:
        pass
    mcp = FastMCP("MAGNA TRACE", stateless_http=True, json_response=True, **kwargs)

    def out(session: Session, result: tuple[str, dict]) -> dict:
        text, compact = result
        return {**compact, "case_id": session.case_id, "question_id": session.question_id, "message": text}

    @mcp.tool(description="Open a diagnostic case for one test station (e.g. ST3003). Returns case_id, the open "
                          "question_id, findings with evidence IDs, and the text for the technician." + RELAY)
    async def open_case(station_number: str, time_from: str | None = None, time_to: str | None = None,
                        serial_number: str | None = None) -> dict:
        session = Session()
        scope = {"from": time_from, "to": time_to, "serial_number": serial_number}
        return out(session, await toolbox.open_case(session, station_number, **scope))

    @mcp.tool(description="Show the stored source behind one evidence ID of a case. For a deviation use the "
                          "finding's calculation_id; for a raw value or limit its evidence_id." + RELAY)
    async def get_evidence(case_id: str, evidence_id: str) -> dict:
        session = Session()
        session.case_id = case_id.strip().lower()
        return out(session, await toolbox.get_evidence(session, evidence_id))

    @mcp.tool(description="Record the technician's reply to the open question of a case. Call it every time the "
                          "technician answers that question, even 'no' or 'I don't know', before replying." + RELAY)
    async def record_answer(case_id: str, question_id: str, answer_text: str) -> dict:
        session = Session()
        session.case_id, session.question_id = case_id.strip().lower(), question_id.strip().lower()
        return out(session, await toolbox.record_answer(session, answer_text))

    @mcp.tool(description="Handover summary of a case for the next shift." + RELAY)
    async def get_handover(case_id: str) -> dict:
        session = Session()
        session.case_id = case_id.strip().lower()
        return out(session, await toolbox.get_handover(session))

    @mcp.tool(description="List known station identifiers; use only when the station is unclear or not found.")
    async def list_stations(q: str | None = None) -> dict:
        session = Session()
        return out(session, await toolbox.list_stations(session, q))

    return mcp


class KeyGuard:
    """Fail-closed X-API-Key check in front of the mounted MCP app."""

    def __init__(self, app, check) -> None:
        self.app, self.check = app, check

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "http":
            keys = [v.decode("latin-1") for k, v in scope.get("headers", []) if k == b"x-api-key"]
            if len(keys) != 1 or not self.check(keys[0]):
                scope.setdefault("b_request_id", "unassigned")
                await error_response(scope, Failure("UNAUTHORIZED", "Valid connector credentials are required", 401))(scope, receive, send)
                return
        await self.app(scope, receive, send)

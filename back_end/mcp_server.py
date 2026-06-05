import json

from mcp.server.fastmcp import FastMCP

from back_end.services.clearance_facade import clearance_facade


clearance_mcp = FastMCP(
    name="Third Party Clearance",
    stateless_http=True,
    json_response=True,
)
clearance_mcp.settings.streamable_http_path = "/"


def _json_text(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


@clearance_mcp.tool(
    name="clearance.start_analysis",
    description="Start OSS third-party clearance analysis from LicenseInfo HTML content.",
)
def clearance_start_analysis(
    html_content: str,
    filename: str = "license-info.html",
) -> dict:
    return clearance_facade.start_analysis_from_content(html_content, filename)


@clearance_mcp.tool(
    name="clearance.chat",
    description="Send a confirmation or follow-up message to an existing clearance session.",
)
def clearance_chat(session_id: str, message: str) -> dict:
    return clearance_facade.chat(session_id, message)


@clearance_mcp.tool(
    name="clearance.get_session",
    description="Get clearance session state, progress, current items, and download availability.",
)
def clearance_get_session(session_id: str) -> dict:
    return clearance_facade.get_session(session_id)


@clearance_mcp.tool(
    name="clearance.generate_report",
    description="Generate the final OSS Readme report once confirmations are complete.",
)
def clearance_generate_report(session_id: str, force: bool = False) -> dict:
    return clearance_facade.generate_report(session_id, force=force)


@clearance_mcp.resource("clearance://sessions/{session_id}/summary")
def clearance_session_summary(session_id: str) -> str:
    return _json_text(clearance_facade.get_session(session_id))


@clearance_mcp.resource("clearance://sessions/{session_id}/checked-risk")
def clearance_checked_risk(session_id: str) -> str:
    return _json_text(clearance_facade.checked_risk_resource(session_id))


@clearance_mcp.resource("clearance://sessions/{session_id}/report")
def clearance_report(session_id: str) -> str:
    return _json_text(clearance_facade.report_resource(session_id))


@clearance_mcp.prompt()
def clearance_review_session(session_id: str = "") -> str:
    target = f" for session {session_id}" if session_id else ""
    return (
        f"You are reviewing a third-party clearance workflow{target}. "
        "Use clearance.get_session to inspect current state, read the summary resource for context, "
        "then call clearance.chat with concise confirmation decisions. Confirm items only when the "
        "risk justification and component context are sufficient; otherwise ask for clarification."
    )


@clearance_mcp.prompt()
def clearance_risk_triage(session_id: str = "") -> str:
    target = f" for session {session_id}" if session_id else ""
    checked_risk_resource = (
        f"clearance://sessions/{session_id}/checked-risk"
        if session_id
        else "clearance://sessions/{session_id}/checked-risk"
    )
    return (
        f"Focus on high and medium OSS license risks{target}. "
        f"Read {checked_risk_resource} when a session id is available, "
        "group findings by severity, and recommend whether each item should be confirmed, discarded, "
        "or escalated for human legal review."
    )

from pathlib import Path

import pytest

from back_end.items_utils.item_types import ConfirmationStatus
from back_end.services.clearance_facade import ClearanceError, ClearanceFacade
from back_end.services.session_store import SessionStore


class FakeState:
    def __init__(self, value):
        self.value = value


class FakeFlow:
    def __init__(self, initial_state=ConfirmationStatus.OEM.value):
        self.current_state = FakeState(initial_state)

    def process(self, content):
        self.current_state = FakeState(ConfirmationStatus.PRODUCTOVERVIEW.value)
        return {"current_state": self.current_state}


class FakeMarkdownBuilder:
    def save_document(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text("# report\n", encoding="utf-8")


class FakeHandlerFactory:
    def __init__(self):
        self.md = FakeMarkdownBuilder()


class FakeChatService:
    def __init__(self):
        self.chat_flow = FakeFlow()
        self.handler_factory = FakeHandlerFactory()
        self.bot = object()

    def initialize_chat(self, shared):
        shared["checkedRisk"] = [
            {
                "title": "GPL",
                "CheckedLevel": "high",
                "Justification": "Strong copyleft",
                "status": "",
            }
        ]
        return shared

    def get_instructions(self, status):
        return f"instructions for {status}"

    def process_user_input(self, shared, user_input, status):
        shared["current_component_idx"] = 0
        return ConfirmationStatus.OSSGENERATION.value, shared, ["confirmed"]


def make_facade(tmp_path):
    def analysis_runner(html_path):
        return {"html_path": html_path, "parsedHtml": {}, "riskBot": object()}

    def report_runner(shared):
        out_dir = tmp_path / "downloads" / shared["session_id"]
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "Final_OSS_Readme.docx").write_bytes(b"docx")
        shared["reconstructedHtml"] = "<html>report</html>"
        return shared

    return ClearanceFacade(
        store=SessionStore(),
        upload_dir=tmp_path / "uploads",
        mcp_upload_dir=tmp_path / "uploads" / "mcp",
        download_dir=tmp_path / "downloads",
        analysis_runner=analysis_runner,
        report_runner=report_runner,
        chat_service_factory=FakeChatService,
    )


def test_start_analysis_from_content_creates_session_and_upload(tmp_path):
    facade = make_facade(tmp_path)

    result = facade.start_analysis_from_content("<html></html>", "license-info.html")

    assert result["session_id"]
    assert result["status"] == ConfirmationStatus.OEM.value
    assert (tmp_path / "uploads" / "mcp" / "license-info.html").exists()
    summary = facade.get_session(result["session_id"])
    assert summary["progress"]["license"]["total"] == 1
    assert summary["progress"]["license"]["pending"] == 1


def test_start_analysis_rejects_path_traversal(tmp_path):
    facade = make_facade(tmp_path)

    with pytest.raises(ClearanceError):
        facade.start_analysis_from_content("<html></html>", "../license-info.html")


def test_generate_report_requires_ready_state_unless_forced(tmp_path):
    facade = make_facade(tmp_path)
    result = facade.start_analysis_from_content("<html></html>", "license-info.html")

    with pytest.raises(ClearanceError):
        facade.generate_report(result["session_id"])

    forced = facade.generate_report(result["session_id"], force=True)
    assert forced["download"]["available"] is True


def test_chat_generates_report_when_flow_reaches_oss_generation(tmp_path):
    facade = make_facade(tmp_path)
    result = facade.start_analysis_from_content("<html></html>", "license-info.html")

    response = facade.chat(result["session_id"], "next")

    assert response["status"] == ConfirmationStatus.PRODUCTOVERVIEW.value
    assert response["download"]["available"] is True
    report = facade.report_resource(result["session_id"])
    assert report["reconstructedHtml"] == "<html>report</html>"


def test_mcp_module_import_is_available_when_sdk_is_installed():
    pytest.importorskip("mcp")
    import back_end.mcp_server as mcp_server

    assert mcp_server.clearance_mcp is not None

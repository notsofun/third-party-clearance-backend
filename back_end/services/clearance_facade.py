import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from back_end.items_utils.item_types import ConfirmationStatus, ItemStatus, TYPE_CONFIG
from back_end.services.session_store import SESSION_STORE, ClearanceSession, SessionStore
from log_config import get_logger


logger = get_logger(__name__)


class ClearanceError(ValueError):
    """Domain error that should be returned as a structured client error."""


class ClearanceFacade:
    """Application-facing API shared by FastAPI routes and MCP tools."""

    SAFE_FILENAME = re.compile(r"^[A-Za-z0-9._ -]+$")

    def __init__(
        self,
        store: SessionStore = SESSION_STORE,
        upload_dir: Path = Path("uploads"),
        mcp_upload_dir: Path = Path("uploads/mcp"),
        download_dir: Path = Path("downloads"),
        analysis_runner: Optional[Callable[[str], Dict[str, Any]]] = None,
        report_runner: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        chat_service_factory: Optional[Callable[[], Any]] = None,
    ):
        self.store = store
        self.upload_dir = upload_dir
        self.mcp_upload_dir = mcp_upload_dir
        self.download_dir = download_dir
        self.analysis_runner = analysis_runner
        self.report_runner = report_runner
        self.chat_service_factory = chat_service_factory

    def start_analysis_from_content(
        self,
        html_content: str,
        filename: str = "license-info.html",
    ) -> Dict[str, Any]:
        if not isinstance(html_content, str) or not html_content.strip():
            raise ClearanceError("html_content must be a non-empty string")

        safe_name = self._safe_filename(filename, default="license-info.html", suffix=".html")
        file_path = self._write_bytes(
            self.mcp_upload_dir,
            safe_name,
            html_content.encode("utf-8"),
        )
        return self.start_analysis_from_file(file_path, source="mcp")

    def start_analysis_from_bytes(
        self,
        file_content: bytes,
        filename: str,
        *,
        source: str = "rest",
    ) -> Dict[str, Any]:
        if not file_content:
            raise ClearanceError("Uploaded file is empty")

        safe_name = self._safe_filename(filename, default="license-info.html", suffix=".html")
        target_dir = self.upload_dir if source == "rest" else self.mcp_upload_dir
        file_path = self._write_bytes(target_dir, safe_name, file_content)
        return self.start_analysis_from_file(file_path, source=source)

    def start_analysis_from_file(self, file_path: Path, *, source: str = "rest") -> Dict[str, Any]:
        if not file_path.exists():
            raise ClearanceError(f"Input file not found: {file_path}")

        shared = self._run_analysis(str(file_path.absolute()))
        chat_service = self._new_chat_service()
        updated_shared = chat_service.initialize_chat(shared)
        status = chat_service.chat_flow.current_state.value
        initial_message = chat_service.get_instructions(status)
        session_id = str(uuid.uuid4())

        state = status if not updated_shared.get("all_confirmed") else ConfirmationStatus.COMPLETED.value
        self.store.create(
            session_id=session_id,
            shared=updated_shared,
            state=state,
            chat_service=chat_service,
            metadata={"source": source, "input_file": str(file_path)},
        )

        return {
            "session_id": session_id,
            "components": updated_shared.get("toBeConfirmedComps", []),
            "message": initial_message,
            "status": state,
            "summary": self._build_summary(session_id, updated_shared, state),
        }

    def chat(self, session_id: str, message: str) -> Dict[str, Any]:
        session = self._require_session(session_id)
        chat_service = session.chat_service
        status = chat_service.chat_flow.current_state.value

        if status == ConfirmationStatus.COMPLETED.value:
            session.state = ConfirmationStatus.COMPLETED.value
            return {
                "status": ConfirmationStatus.COMPLETED.value,
                "message": "We have finished all checking in current session, please reupload a new license info file to start a new session.",
            }

        status, updated_shared, reply = chat_service.process_user_input(
            session.shared,
            message,
            status,
        )

        download_info = None
        if status == ConfirmationStatus.OSSGENERATION.value and not session.report_generated:
            session.state = status
            report_result = self.generate_report(session_id, force=True, shared_override=updated_shared)
            updated_shared = session.shared
            status = session.state
            download_info = report_result.get("download")

        if status == ConfirmationStatus.PRODUCTOVERVIEW.value and not session.product_report_saved:
            self._save_product_report(session_id, chat_service)
            session.product_report_saved = True

        self.store.update(
            session_id,
            state=status,
            shared=updated_shared,
            chat_service=chat_service,
        )

        response = {
            "status": status,
            "message": reply,
            "current_component_idx": updated_shared.get("current_component_idx"),
            "summary": self._build_summary(session_id, updated_shared, status),
        }
        if download_info:
            response["download"] = download_info
        return response

    def get_session(self, session_id: str) -> Dict[str, Any]:
        session = self._require_session(session_id)
        return self._build_summary(session_id, session.shared, session.state)

    def generate_report(
        self,
        session_id: str,
        *,
        force: bool = False,
        shared_override: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        session = self._require_session(session_id)
        shared = shared_override or session.shared

        if session.report_generated and self._report_path(session_id).exists():
            return {
                "session_id": session_id,
                "status": session.state,
                "download": self._download_info(session_id),
                "summary": self._build_summary(session_id, shared, session.state),
            }

        if not force and not self._is_report_ready(session.state):
            raise ClearanceError(
                "Report is not ready yet. Finish confirmations first, or call with force=True."
            )

        shared["session_id"] = session_id
        self._session_download_dir(session_id).mkdir(parents=True, exist_ok=True)
        updated_shared = self._run_report(shared)
        updated_shared["download_url"] = self._absolute_download_url(session_id)

        session.shared = updated_shared
        session.report_generated = True

        if session.state == ConfirmationStatus.OSSGENERATION.value:
            content = {"shared": updated_shared, "status": "next"}
            result_in_flow = session.chat_service.chat_flow.process(content)
            session.state = result_in_flow["current_state"].value

        return {
            "session_id": session_id,
            "status": session.state,
            "download": self._download_info(session_id),
            "summary": self._build_summary(session_id, updated_shared, session.state),
        }

    def save_upload_bytes(self, file_content: bytes, filename: str) -> Path:
        safe_name = self._safe_filename(filename, default="upload.bin")
        return self._write_bytes(self.upload_dir, safe_name, file_content)

    def analyze_contract(self, session_id: str, file_path: Path) -> Dict[str, Any]:
        session = self._require_session(session_id)
        chat_service = session.chat_service
        analysis_result = chat_service.bot.contract_check(str(file_path))
        session.contract_analysis = analysis_result

        old_status = chat_service.chat_flow.current_state.value
        content = {"shared": session.shared, "status": "next"}
        result_in_flow = chat_service.chat_flow.process(content)
        updated_status = result_in_flow["current_state"].value
        handler = chat_service.handler_factory.get_handler(updated_status, chat_service.bot)
        updated_status, updated_shared, message = chat_service._status_check(
            session.shared,
            updated_status,
            old_status,
            "next",
            None,
            handler,
        )

        self.store.update(
            session_id,
            state=updated_status,
            shared=updated_shared,
            chat_service=chat_service,
        )

        return {
            "status": updated_status,
            "message": message,
            "contract_analysis": analysis_result,
        }

    def checked_risk_resource(self, session_id: str) -> Dict[str, Any]:
        session = self._require_session(session_id)
        return {
            "session_id": session_id,
            "checkedRisk": self._json_safe(session.shared.get("checkedRisk", [])),
        }

    def report_resource(self, session_id: str) -> Dict[str, Any]:
        session = self._require_session(session_id)
        report_path = self._report_path(session_id)
        return {
            "session_id": session_id,
            "status": session.state,
            "download": self._download_info(session_id),
            "report_exists": report_path.exists(),
            "reconstructedHtml": session.shared.get("reconstructedHtml", ""),
        }

    def _run_analysis(self, html_path: str) -> Dict[str, Any]:
        if self.analysis_runner:
            return self.analysis_runner(html_path)
        from main import run_analysis

        return run_analysis(html_path)

    def _run_report(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        if self.report_runner:
            return self.report_runner(shared)
        from main import run_report

        return run_report(shared)

    def _new_chat_service(self):
        if self.chat_service_factory:
            return self.chat_service_factory()
        from back_end.services.chat_service import ChatService

        return ChatService()

    def _safe_filename(self, filename: str, *, default: str, suffix: Optional[str] = None) -> str:
        candidate = (filename or default).strip() or default
        if Path(candidate).name != candidate or Path(candidate).is_absolute() or ".." in Path(candidate).parts:
            raise ClearanceError("filename must not contain path separators or parent-directory references")
        if not self.SAFE_FILENAME.match(candidate):
            raise ClearanceError("filename contains unsupported characters")
        if suffix and not candidate.lower().endswith(suffix):
            raise ClearanceError(f"filename must end with {suffix}")
        return candidate

    def _write_bytes(self, directory: Path, filename: str, content: bytes) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        file_path = directory / filename
        file_path.write_bytes(content)
        return file_path

    def _require_session(self, session_id: str) -> ClearanceSession:
        try:
            return self.store.require(session_id)
        except KeyError as exc:
            raise ClearanceError(str(exc)) from exc

    def _build_summary(self, session_id: str, shared: Dict[str, Any], state: str) -> Dict[str, Any]:
        current_component_idx = shared.get("current_component_idx")
        components = shared.get("toBeConfirmedComps", [])
        return {
            "session_id": session_id,
            "status": state,
            "components": self._json_safe(components),
            "current_component_idx": current_component_idx if current_component_idx is not None else -1,
            "progress": self._progress_by_item_type(shared),
            "current_items": self._current_items_by_type(shared),
            "download": self._download_info(session_id),
        }

    def _progress_by_item_type(self, shared: Dict[str, Any]) -> Dict[str, Dict[str, int]]:
        progress = {}
        for item_type, config in TYPE_CONFIG.items():
            items = shared.get(config.get("items_key"), [])
            if not isinstance(items, list):
                continue
            completed = 0
            pending = 0
            for item in items:
                status = item.get("status", "") if isinstance(item, dict) else ""
                if ItemStatus.is_terminal_status(status):
                    completed += 1
                else:
                    pending += 1
            progress[item_type.value] = {
                "total": len(items),
                "completed": completed,
                "pending": pending,
            }
        return progress

    def _current_items_by_type(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        current_items = {}
        for item_type, config in TYPE_CONFIG.items():
            items = shared.get(config.get("items_key"), [])
            current_key = config.get("current_key")
            current_idx = shared.get(current_key, 0)
            if isinstance(items, list) and 0 <= current_idx < len(items):
                current_items[item_type.value] = self._json_safe(items[current_idx])
        return current_items

    def _json_safe(self, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            return {str(k): self._json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._json_safe(v) for v in value]
        try:
            json.dumps(value)
            return value
        except TypeError:
            return str(value)

    def _is_report_ready(self, status: str) -> bool:
        ready_states = {
            ConfirmationStatus.OSSGENERATION.value,
            ConfirmationStatus.PRODUCTOVERVIEW.value,
            ConfirmationStatus.COMPONENTOVERVIEW.value,
            ConfirmationStatus.COMMONRULES.value,
            ConfirmationStatus.OBLIGATIONS.value,
            ConfirmationStatus.INTERACTION.value,
            ConfirmationStatus.COPYLEFT.value,
            ConfirmationStatus.SPECIAL_CONSIDERATION.value,
            ConfirmationStatus.COMPLETED.value,
        }
        return status in ready_states

    def _save_product_report(self, session_id: str, chat_service: Any) -> None:
        report_dir = self._session_download_dir(session_id) / "product_clearance"
        report_dir.mkdir(parents=True, exist_ok=True)
        chat_service.handler_factory.md.save_document(str(report_dir / "report.md"))

    def _session_download_dir(self, session_id: str) -> Path:
        return self.download_dir / session_id

    def _report_path(self, session_id: str) -> Path:
        return self._session_download_dir(session_id) / "Final_OSS_Readme.docx"

    def _download_info(self, session_id: str) -> Dict[str, Any]:
        return {
            "available": self._report_path(session_id).exists(),
            "url": f"download/{session_id}",
            "filename": "Final_OSS_Readme.docx",
        }

    def _absolute_download_url(self, session_id: str) -> str:
        try:
            from back_end.config import settings

            if not settings.API_BASE_URL:
                settings.init_api_base_url()
            base_url = settings.API_BASE_URL
        except Exception:
            base_url = "http://127.0.0.1:8000"
        return f"{base_url}/download/{session_id}"


clearance_facade = ClearanceFacade()

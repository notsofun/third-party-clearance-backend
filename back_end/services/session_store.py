from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Dict, Optional


@dataclass
class ClearanceSession:
    """Runtime state shared by REST endpoints and MCP tools."""

    shared: Dict[str, Any]
    state: str
    chat_service: Any
    report_generated: bool = False
    product_report_saved: bool = False
    contract_analysis: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class SessionStore:
    """Small in-memory session registry for the MVP."""

    def __init__(self):
        self._sessions: Dict[str, ClearanceSession] = {}
        self._lock = RLock()

    @property
    def sessions(self) -> Dict[str, ClearanceSession]:
        return self._sessions

    def create(
        self,
        session_id: str,
        shared: Dict[str, Any],
        state: str,
        chat_service: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ClearanceSession:
        with self._lock:
            session = ClearanceSession(
                shared=shared,
                state=state,
                chat_service=chat_service,
                metadata=metadata or {},
            )
            self._sessions[session_id] = session
            return session

    def get(self, session_id: str) -> Optional[ClearanceSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def require(self, session_id: str) -> ClearanceSession:
        session = self.get(session_id)
        if not session:
            raise KeyError(f"Session {session_id} not found")
        return session

    def update(
        self,
        session_id: str,
        *,
        shared: Optional[Dict[str, Any]] = None,
        state: Optional[str] = None,
        chat_service: Any = None,
    ) -> ClearanceSession:
        with self._lock:
            session = self.require(session_id)
            if shared is not None:
                session.shared = shared
            if state is not None:
                session.state = state
            if chat_service is not None:
                session.chat_service = chat_service
            return session


SESSION_STORE = SessionStore()

"""Native chat SDK gateway (contract 10; owner Atharv).

Implements the gateway duck-type Vandit's ``/api/v1/chat/*`` routes consume:

* ``create_session() -> ChatSession``
* ``send_message(session_id, text) -> ChatResponse``

One agent instance per session (``run`` starts a conversation, ``continue``
adds turns). The gateway extracts ``[[ev_<64hex>]]`` markers from the agent
answer, resolves them through the single ``VerityService`` evidence path and
returns resolved ``Evidence[]`` plus the ``citations`` marker list. Unresolved
markers stay visible in the message text for the UI's unresolved-citation
state — the gateway never fabricates a citation label (contract 07/10).

The gateway owns NO retrieval, evidence construction or coverage logic and
never opens SQLite. When the agent runtime is unavailable, both methods raise
``SDK_UNAVAILABLE`` — never a fake answer, never a non-SDK agent.
"""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timezone
from uuid import uuid4

from verity.errors import VerityError
from verity.evidence import CITATION_MARKER_RE
from verity.models import ChatMessage, ChatResponse, ChatSession
from .runtime import ClineSdkRuntime

SCHEMA_VERSION = "1.0.0"


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class _SyncService:
    """Synchronous facade over the async VerityService.

    The chat routes call the gateway synchronously from inside their event
    loop; a dedicated background loop keeps the async service contract intact
    without blocking the caller's loop.
    """

    def __init__(self, service) -> None:
        self._service = service
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()

    def call(self, name: str, *args):
        coro = getattr(self._service, name)(*args)
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout=30)


class SdkChatGateway:
    """Contract-10 SDK gateway: session map, markers, evidence resolution."""

    def __init__(self, service, runtime=None) -> None:
        self._sync = _SyncService(service)
        self._runtime = runtime if runtime is not None else ClineSdkRuntime()
        self._sessions: dict[str, dict] = {}

    # -- Vandit's duck-type (verity/http/routes.py V8) ------------------------

    def create_session(self) -> ChatSession:
        if not self._runtime.available:
            raise VerityError(
                "SDK_UNAVAILABLE",
                "native chat requires the Cline SDK gateway (contract 10), "
                "which is not configured",
            )
        session_id = str(uuid4())
        self._sessions[session_id] = {
            "agent": self._runtime.create_agent(),
            "started": False,
        }
        return ChatSession(
            schema_version=SCHEMA_VERSION,
            session_id=session_id,
            created_at=_utcnow(),
        )

    def send_message(self, session_id: str, text: str) -> ChatResponse:
        if not isinstance(session_id, str):
            raise VerityError("INVALID_REQUEST", "session_id must be a UUIDv4 string",
                              {"field": "session_id"})
        try:
            parsed = __import__("uuid").UUID(session_id)
            if parsed.version != 4 or str(parsed) != session_id:
                raise ValueError
        except ValueError:
            raise VerityError(
                "INVALID_REQUEST", "session_id must be a UUIDv4 string",
                {"field": "session_id"},
            ) from None
        if not isinstance(text, str) or not 1 <= len(text) <= 8000:
            raise VerityError(
                "INVALID_REQUEST", "text must be a string of 1-8000 characters",
                {"field": "text"},
            )
        session = self._sessions.get(session_id)
        if session is None:
            raise VerityError(
                "SESSION_NOT_FOUND", "no such chat session",
                {"session_id": session_id},
            )
        if not self._runtime.available:
            raise VerityError(
                "SDK_UNAVAILABLE",
                "native chat requires the Cline SDK gateway (contract 10), "
                "which is not configured",
            )
        agent = session["agent"]
        if session["started"]:
            answer = self._runtime.continue_turn(agent, text)
        else:
            answer = self._runtime.run(agent, text)
            session["started"] = True

        # Extract markers, resolve through EvidenceService, flag the rest.
        citations, evidence = self._resolve_markers(answer)
        return ChatResponse(
            schema_version=SCHEMA_VERSION,
            session_id=session_id,
            message=ChatMessage(
                role="assistant",
                text=answer,
                citations=citations,
                created_at=_utcnow(),
            ),
            evidence=evidence,
        )

    # -- marker resolution (contracts 07/10) ---------------------------------

    def _resolve_markers(self, answer: str) -> tuple[list[str], list]:
        citations: list[str] = []
        evidence: list = []
        seen: set[str] = set()
        for match in CITATION_MARKER_RE.finditer(answer):
            marker = match.group(0)[2:-2]  # [[ev_...]] -> ev_...
            if marker in seen:
                continue
            seen.add(marker)
            try:
                lookup = self._sync.call("get_evidence", marker, 1000)
            except VerityError:
                continue  # unresolved marker: stays in text for the UI to flag
            citations.append(marker)
            evidence.append(lookup.evidence)
        return citations, evidence